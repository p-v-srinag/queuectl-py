import typer
import json
from ..models import JobState
from ..database import list_jobs_by_state

app = typer.Typer(name="list", help="List jobs by state.")

@app.callback(invoke_without_command=True)
def list_jobs(
    state: JobState = typer.Option(
        JobState.PENDING, 
        "--state", "-s", 
        help="The job state to list.",
        case_sensitive=False
    )
):
    """
    Lists jobs by their state.
    """
    jobs = list_jobs_by_state(state)
    if not jobs:
        typer.echo(f"No jobs found in state: {state.value}")
        return
    
    typer.echo(f"--- Jobs in '{state.value}' state ---")
    for job in jobs:
        typer.echo(json.dumps(job.to_dict(), indent=2))