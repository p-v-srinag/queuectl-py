import typer
from ..worker import start_workers, stop_workers
from ..database import close_db_conn  # <-- IMPORT THE NEW FUNCTION

app = typer.Typer(name="worker", help="Manage worker processes.")

@app.command("start")
def worker_start(
    count: int = typer.Option(1, "--count", "-c", help="Number of worker processes to start.")
):
    """Starts one or more worker processes in the background."""
    if count < 1:
        typer.secho("Error: Count must be at least 1.", fg=typer.colors.RED)
        raise typer.Exit(1)
    
    # --- THIS IS THE FIX ---
    # Close the DB connection opened by the main_callback
    # This ensures the child processes don't inherit a stale connection.
    close_db_conn()
    # --- END OF FIX ---
    
    start_workers(count)

@app.command("stop")
def worker_stop():
    """Stops all running worker processes gracefully."""
    stop_workers()