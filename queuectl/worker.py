import subprocess
import time
import signal
import os
import sys
from datetime import datetime
import psutil
from typing import List, Dict

from .models import Job, JobState
# We must import init_db separately for the fix
from .database import get_next_pending_job_atomic, update_job, move_to_dlq, init_db
from .config import get_config_value, PID_FILE

# Flag to control graceful shutdown
shutdown_flag = False

def signal_handler(signum, frame):
    """Handles termination signals for graceful shutdown."""
    global shutdown_flag
    print(f"Signal {signum} received, shutting down gracefully...")
    shutdown_flag = True

def execute_job(job: Job) -> bool:
    """
    Executes a job's command using subprocess.
    Returns True on success (exit code 0), False otherwise.
    """
    print(f"[Worker {os.getpid()}] Processing job {job.id}: {job.command}")
    try:
        # Using shlex.split might be safer, but for this spec,
        # shell=True executes the raw command string.
        # This is a security risk if commands are from untrusted users,
        # but matches the 'echo "Hello World"' spec.
        result = subprocess.run(
            job.command,
            shell=True,
            check=True,  # Raises CalledProcessError on non-zero exit
            capture_output=True,
            text=True,
            timeout=300 # 5-minute timeout
        )
        print(f"[Worker {os.getpid()}] Job {job.id} completed. Output:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[Worker {os.getpid()}] Job {job.id} failed. Error:\n{e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        print(f"[Worker {os.getpid()}] Job {job.id} timed out.")
        return False
    except Exception as e:
        print(f"[Worker {os.getpid()}] Job {job.id} failed with unexpected error: {e}")
        return False

def run_worker():
    """The main loop for a single worker process."""
    
    # --- THIS IS THE FIX ---
    # Initialize the DB *within* the new child process.
    # This creates a fresh, safe connection.
    init_db()
    # --- END OF FIX ---
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"[Worker {os.getpid()}] Started and waiting for jobs...")
    
    while not shutdown_flag:
        job = None
        try:
            job = get_next_pending_job_atomic()
            
            if job:
                job.attempts += 1
                success = execute_job(job)
                
                if success:
                    job.state = JobState.COMPLETED
                    update_job(job)
                else:
                    handle_failed_job(job)
                
            else:
                # No jobs, sleep for a bit to avoid busy-waiting
                time.sleep(1)
                
        except Exception as e:
            print(f"[Worker {os.getpid()}] Error in worker loop: {e}")
            if job:
                # Ensure a job isn't stuck in processing if worker crashes
                handle_failed_job(job) # Or reset to pending
            time.sleep(1)
            
    print(f"[Worker {os.getpid()}] Shutdown complete.")

def handle_failed_job(job: Job):
    """Handles retry logic and DLQ promotion for a failed job."""
    config_max_retries = get_config_value("max_retries")
    backoff_base = get_config_value("backoff_base")

    # Ensure job's max_retries is in sync with config, or use its own
    max_retries = job.max_retries if job.max_retries > 0 else config_max_retries
    
    if job.attempts >= max_retries:
        print(f"[Worker {os.getpid()}] Job {job.id} failed. Max retries ({max_retries}) reached. Moving to DLQ.")
        move_to_dlq(job)
    else:
        # It failed, but can be retried
        job.state = JobState.FAILED
        update_job(job) # Record the failure and attempt count
        
        # Calculate exponential backoff
        # We don't actually sleep here. We set it back to PENDING
        # but it will be picked up later.
        # A true backoff would involve a 'run_at' time.
        # For this spec, we'll just log the "delay" and re-queue.
        delay = backoff_base ** job.attempts
        print(f"[Worker {os.getpid()}] Job {job.id} failed. Retrying (attempt {job.attempts}/{max_retries}). Next attempt after ~{delay}s.")
        
        # To simulate backoff, we'll just put it back to PENDING.
        # In a real system, we'd use a 'run_at' field.
        # For simplicity, we just put it back at the end of the line.
        job.state = JobState.PENDING
        update_job(job) # This updates 'updated_at', so it goes to the "end"
        
        # A simple sleep to prevent a fast-failing job from
        # hammering the CPU. This is a *worker-side* delay.
        time.sleep(delay)

def start_workers(count: int):
    """Starts a specified number of worker processes."""
    pids = []
    print(f"Starting {count} worker(s)...")
    for _ in range(count):
        pid = os.fork()
        if pid == 0:
            # This is the child process
            try:
                run_worker()
            except KeyboardInterrupt:
                pass # Child process exits
            sys.exit(0)
        else:
            # This is the parent process
            pids.append(pid)
    
    # Store PIDs
    with open(PID_FILE, 'w') as f:
        f.writelines([f"{pid}\n" for pid in pids])
    
    print(f"Workers started with PIDs: {pids}")

def stop_workers():
    """Stops all running worker processes gracefully."""
    if not PID_FILE.exists():
        print("No workers seem to be running (PID file not found).")
        return

    pids_to_remove = []
    if os.path.getsize(PID_FILE) > 0:
        with open(PID_FILE, 'r') as f:
            pids = [int(line.strip()) for line in f if line.strip()]

        if not pids:
            print("No workers PIDs found.")
            os.remove(PID_FILE)
            return

        print(f"Sending SIGTERM to PIDs: {pids}")
        for pid in pids:
            try:
                if psutil.pid_exists(pid):
                    os.kill(pid, signal.SIGTERM)
                else:
                    print(f"PID {pid} not found.")
                pids_to_remove.append(pid)
            except ProcessLookupError:
                print(f"Process {pid} already stopped.")
                pids_to_remove.append(pid)
            except Exception as e:
                print(f"Error stopping {pid}: {e}")
                
    # Clean up PID file
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    print("Stop signal sent. Workers will shut down gracefully.")


def get_worker_status() -> List[Dict]:
    """Checks the status of running workers."""
    status = []
    if not PID_FILE.exists():
        return status

    if os.path.getsize(PID_FILE) == 0:
        return status
        
    with open(PID_FILE, 'r') as f:
        pids = [int(line.strip()) for line in f if line.strip()]

    active_pids = []
    for pid in pids:
        try:
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                status.append({
                    "pid": pid,
                    "status": proc.status(),
                    "cpu_percent": proc.cpu_percent(interval=0.01),
                    "memory_mb": proc.memory_info().rss / (1024 * 1024),
                })
                active_pids.append(pid) # Keep tracking this active pid
            else:
                status.append({"pid": pid, "status": "not_found (stale PID)"})
        except psutil.NoSuchProcess:
            status.append({"pid": pid, "status": "stopped"})
        except Exception as e:
            status.append({"pid": pid, "status": f"error: {e}"})

    # Re-write the PID file with only active pids
    with open(PID_FILE, 'w') as f:
        f.writelines([f"{pid}\n" for pid in active_pids])

    return status