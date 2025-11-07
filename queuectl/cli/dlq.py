import typer
import json
from ..models import JobState
from ..database import list_jobs_by_state, find_dlq_job, retry_dlq_job

app = typer.Typer(name="dlq", help="Manage the Dead Letter Queue (DLQ).")

@app.command("list")
def dlq_list():
    """Lists all jobs in the Dead Letter Queue."""
    jobs = list_jobs_by_state(JobState.DEAD)
    if not jobs:
        typer.echo("Dead Letter Queue is empty.")
        return
    
    typer.echo("--- Jobs in Dead Letter Queue ---")
    for job in jobs:
        typer.echo(json.dumps(job.to_dict(), indent=2))

@app.command("retry")
def dlq_retry(
    job_id: str = typer.Argument(..., help="The ID of the DLQ job to retry.")
):
    """Moves a specific job from the DLQ back to the pending queue."""
    job = find_dlq_job(job_id)
    if not job:
        typer.secho(f"Error: Job {job_id} not found in DLQ.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    if retry_dlq_job(job):
        typer.secho(f"Job {job_id} has been re-queued as 'pending'.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Error: Failed to retry job {job_id}.", fg=typer.colors.RED)