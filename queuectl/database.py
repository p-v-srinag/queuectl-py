import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

from .config import DB_PATH, get_config_value
from .models import Job, JobState

# Use thread-local storage for DB connections
local_storage = threading.local()

@contextmanager
def get_db_conn():
    """
    Provides a transactional database connection.
    This context manager handles connection life-cycle and transactions.
    """
    # Check if a connection already exists for this thread
    if not hasattr(local_storage, "connection"):
        # Set timeout to handle potential lock contention
        local_storage.connection = sqlite3.connect(DB_PATH, timeout=10)
        # This is key for getting dict-like rows
        local_storage.connection.row_factory = sqlite3.Row 

    conn = local_storage.connection
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
    # We don't close the connection here; it's managed per-thread.
    # A more robust solution might use a connection pool.

def init_db():
    """Initializes the database schema."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        # Main job queue table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
        # Dead Letter Queue (DLQ) table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dlq (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL,
            max_retries INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
        # Index for efficient pending job queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state_created_at ON jobs (state, created_at);")

def add_job(job: Job) -> bool:
    """Adds a new job to the database."""
    job.max_retries = get_config_value("max_retries")
    try:
        with get_db_conn() as conn:
            conn.execute("""
            INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job.id, job.command, job.state.value, job.attempts, job.max_retries, job.created_at, job.updated_at))
        return True
    except sqlite3.IntegrityError:
        print(f"Error: Job with ID {job.id} already exists.")
        return False

def update_job(job: Job):
    """Updates an existing job's state and metadata."""
    job.updated_at = datetime.utcnow().isoformat()
    with get_db_conn() as conn:
        conn.execute("""
        UPDATE jobs
        SET state = ?, attempts = ?, updated_at = ?
        WHERE id = ?
        """, (job.state.value, job.attempts, job.updated_at, job.id))

def move_to_dlq(job: Job):
    """Atomically moves a job from the main queue to the DLQ."""
    job.state = JobState.DEAD
    job.updated_at = datetime.utcnow().isoformat()
    with get_db_conn() as conn:
        # Insert into DLQ
        conn.execute("""
        INSERT INTO dlq (id, command, state, attempts, max_retries, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job.id, job.command, job.state.value, job.attempts, job.max_retries, job.created_at, job.updated_at))
        
        # Delete from main jobs table
        conn.execute("DELETE FROM jobs WHERE id = ?", (job.id,))

def get_next_pending_job_atomic() -> Optional[Job]:
    """
    Atomically fetches and locks the next pending job.
    This is the most critical part for concurrency.
    """
    with get_db_conn() as conn:
        cursor = conn.cursor()
        
        # SQLite's BEGIN IMMEDIATE acquires a write lock, preventing other
        # workers from picking up jobs until we're done.
        # This is a simple and effective locking mechanism.
        try:
            # Start an immediate transaction to lock
            cursor.execute("BEGIN IMMEDIATE")
            
            # Find the oldest pending job
            cursor.execute("""
            SELECT id, command, state, attempts, max_retries, created_at, updated_at
            FROM jobs
            WHERE state = ?
            ORDER BY created_at
            LIMIT 1
            """, (JobState.PENDING.value,))
            
            row = cursor.fetchone()
            
            if row is None:
                cursor.execute("COMMIT")
                return None
            
            job = Job.from_db_row(row)
            
            # Lock this job by updating its state
            job.state = JobState.PROCESSING
            job.updated_at = datetime.utcnow().isoformat()
            
            cursor.execute("""
            UPDATE jobs
            SET state = ?, updated_at = ?
            WHERE id = ?
            """, (job.state.value, job.updated_at, job.id))
            
            cursor.execute("COMMIT")
            return job
            
        except sqlite3.Error as e:
            # Check for "database is locked" error
            if "locked" in str(e):
                print(f"[Worker {os.getpid()}] Database locked, another worker is picking job. Skipping.")
                cursor.execute("ROLLBACK")
                return None
            print(f"Locking error: {e}")
            cursor.execute("ROLLBACK")
            return None

def get_job_stats() -> Dict[str, int]:
    """Returns a count of jobs by state."""
    stats = {state.value: 0 for state in JobState}
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT state, COUNT(*) as count FROM jobs GROUP BY state")
        for row in cursor.fetchall():
            if row['state'] in stats:
                stats[row['state']] = row['count']
        
        # Get DLQ count
        cursor.execute("SELECT COUNT(*) as count FROM dlq")
        dlq_count = cursor.fetchone()['count']
        stats[JobState.DEAD.value] = dlq_count
    return stats

def list_jobs_by_state(state: JobState) -> List[Job]:
    """Lists all jobs in a given state."""
    table = "dlq" if state == JobState.DEAD else "jobs"
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
        SELECT id, command, state, attempts, max_retries, created_at, updated_at
        FROM {table}
        WHERE state = ?
        ORDER BY created_at
        """, (state.value,))
        
        return [Job.from_db_row(row) for row in cursor.fetchall()]

def find_dlq_job(job_id: str) -> Optional[Job]:
    """Finds a specific job in the DLQ."""
    with get_db_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, command, state, attempts, max_retries, created_at, updated_at
        FROM dlq WHERE id = ?
        """, (job_id,))
        row = cursor.fetchone()
        return Job.from_db_row(row) if row else None

def retry_dlq_job(job: Job) -> bool:
    """Moves a job from the DLQ back to the main queue as pending."""
    job.state = JobState.PENDING
    job.attempts = 0 # Reset attempts
    job.updated_at = datetime.utcnow().isoformat()
    
    with get_db_conn() as conn:
        try:
            # Insert back into main jobs table
            conn.execute("""
            INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job.id, job.command, job.state.value, job.attempts, job.max_retries, job.created_at, job.updated_at))
            
            # Delete from DLQ
            conn.execute("DELETE FROM dlq WHERE id = ?", (job.id,))
            return True
        except sqlite3.Error as e:
            print(f"Error retrying job: {e}")
            return False
def close_db_conn():
    """Closes the connection for the current thread."""
    if hasattr(local_storage, "connection"):
        local_storage.connection.close()
        del local_storage.connection