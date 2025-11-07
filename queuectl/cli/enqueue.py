import typer
import json
import uuid  # <-- ADD THIS LINE
from ..models import Job
from ..database import add_job

app = typer.Typer(name="enqueue", help="Add a new job to the queue.")

@app.callback(invoke_without_command=True)
def enqueue(
    job_spec: str = typer.Argument(
        ..., 
        help='The job specification as a JSON string. e.g. \'{"id":"job1", "command":"sleep 2"}\''
    )
):
    """
    Enqueues a new job.
    """
    try:
        data = json.loads(job_spec)
        if "command" not in data:
            typer.secho("Error: 'command' field is required in JSON.", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        # Use provided ID or generate a new one
        job_id = data.get("id")
        
        job = Job(
            id=job_id if job_id else str(uuid.uuid4()),
            command=data["command"],
        )
        
        if add_job(job):
            typer.secho(f"Successfully enqueued job {job.id}", fg=typer.colors.GREEN)
        else:
            typer.secho(f"Failed to enqueue job {job.id} (ID may exist).", fg=typer.colors.RED)

    except json.JSONDecodeError:
        typer.secho("Error: Invalid JSON string.", fg=typer.colors.RED)
        raise typer.Exit(1)