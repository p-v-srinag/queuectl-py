import typer
import json
from ..database import get_job_stats
from ..worker import get_worker_status

app = typer.Typer(name="status", help="Show summary of all job states & active workers.")

@app.callback(invoke_without_command=True)
def status():
    """
    Shows a summary of job states and active workers.
    """
    typer.echo("--- Job Status Summary ---")
    stats = get_job_stats()
    for state, count in stats.items():
        typer.echo(f"- {state.capitalize()}:\t{count}")
    
    typer.echo("\n--- Active Worker Status ---")
    workers = get_worker_status()
    if not workers:
        typer.echo("No active workers found.")
        return
        
    for worker in workers:
        typer.echo(f"- PID: {worker['pid']}\tStatus: {worker['status']}\tCPU: {worker.get('cpu_percent', 'N/A')}%")