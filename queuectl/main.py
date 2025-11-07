import typer
from .database import init_db

# Create the main Typer app
app = typer.Typer(
    name="queuectl",
    help="A CLI-based background job queue system.",
    no_args_is_help=True
)

# Import and add sub-commands
from .cli import enqueue, worker_cli, status, list_jobs, dlq, config_cli

app.add_typer(enqueue.app, name="enqueue")
app.add_typer(worker_cli.app, name="worker")
app.add_typer(status.app, name="status")
app.add_typer(list_jobs.app, name="list")
app.add_typer(dlq.app, name="dlq")
app.add_typer(config_cli.app, name="config")


@app.callback()
def main_callback():
    """
    Main callback, runs before any command.
    Ensures the database is initialized.
    """
    init_db()

if __name__ == "__main__":
    app()