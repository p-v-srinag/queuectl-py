import typer
import json  # <-- THE FIX IS HERE
from ..config import load_config, save_config, DEFAULT_CONFIG

app = typer.Typer(name="config", help="Manage configuration.")

@app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key to set (e.g., 'max_retries')"),
    value: str = typer.Argument(..., help="Value to set.")
):
    """Sets a configuration value."""
    if key not in DEFAULT_CONFIG:
        typer.secho(f"Error: Unknown config key '{key}'.", fg=typer.colors.RED)
        typer.echo(f"Available keys: {list(DEFAULT_CONFIG.keys())}")
        raise typer.Exit(1)

    # Try to cast value to correct type
    try:
        if isinstance(DEFAULT_CONFIG[key], int):
            typed_value = int(value)
        else:
            typed_value = value
    except ValueError:
        typer.secho(f"Error: Invalid value type for '{key}'. Expected {type(DEFAULT_CONFIG[key])}.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    config = load_config()
    config[key] = typed_value
    save_config(config)
    typer.secho(f"Config updated: {key} = {typed_value}", fg=typer.colors.GREEN)

@app.command("show")
def config_show():
    """Shows the current configuration."""
    config = load_config()
    typer.echo(json.dumps(config, indent=2))