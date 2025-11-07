import uuid
import sqlite3
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

class JobState(str, Enum):
    """Enumeration of possible job states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"

@dataclass
class Job:
    """
    Represents a single job in the queue.
    We use dataclasses for clear, typed definitions.
    """
    command: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: JobState = JobState.PENDING
    attempts: int = 0
    max_retries: int = field(default_factory=lambda: 3) # Can be overridden by config
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Helper methods for JSON/DB serialization
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "command": self.command,
            "state": self.state.value,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: dict) -> 'Job':
        return Job(
            id=data["id"],
            command=data["command"],
            state=JobState(data["state"]),
            attempts=data["attempts"],
            max_retries=data["max_retries"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
    
    @staticmethod
    def from_db_row(row: tuple) -> 'Job': # <-- THIS IS THE CORRECTED LINE
        """Creates a Job object from a database row tuple."""
        # Check if row is a dict (from row_factory) or tuple
        if isinstance(row, sqlite3.Row) or isinstance(row, dict):
            return Job(
                id=row["id"],
                command=row["command"],
                state=JobState(row["state"]),
                attempts=row["attempts"],
                max_retries=row["max_retries"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        else: # Fallback for standard tuple
            return Job(
                id=row[0],
                command=row[1],
                state=JobState(row[2]),
                attempts=row[3],
                max_retries=row[4],
                created_at=row[5],
                updated_at=row[6],
            )