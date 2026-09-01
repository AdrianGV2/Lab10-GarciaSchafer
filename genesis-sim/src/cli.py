"""Command-line entry points for the Manito Genesis simulator.

Four ways to launch, so the way you run the simulator is a choice at the
command line rather than a field buried in a scenario file:

    simctl serve      headless, with the API the web front end talks to
    simctl viewer     the native Genesis window, for looking at a scene
    simctl run        one scenario + one script, no UI, exits with its code
    simctl validate   parse and check scenarios without starting physics
"""

import logging
import multiprocessing as mp
import sys
from pathlib import Path
from typing import Optional

import typer

from src.settings import PROJECT_ROOT, Settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = typer.Typer(name="simctl", help="Manito Genesis simulator", no_args_is_help=True)

IDLE = "idle"


def _configure_logging(verbose: bool) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def _resolve_scenario(scenario: str) -> str:
    """Check a scenario exists before spending 30 seconds building physics."""
    if scenario == IDLE:
        return IDLE

    from src.core.scenario import ScenarioError, load_scenario

    try:
        config = load_scenario(scenario)
    except ScenarioError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    return str(config.path)


def _build_stack(settings: Settings, show_viewer: bool, verbose: bool, with_api: bool):
    """Wire up the tracker, command queue, API and supervisor."""
    from src.runtime.bridges import MPQueueAdapter
    from src.runtime.supervisor import Supervisor
    from src.telemetry.tracker import TelemetryTracker

    tracker = TelemetryTracker()
    mp_queue = mp.Queue(maxsize=100)
    command_queue = MPQueueAdapter(mp_queue)

    publish_frame = lambda frame: None
    if with_api:
        from src.api.server import start_api_server

        _, api_app = start_api_server(settings, command_queue, tracker)
        publish_frame = api_app.state.video.publish
        logger.info("API listening on http://%s:%s", settings.host, settings.port)

    supervisor = Supervisor(
        settings,
        tracker,
        mp_queue,
        publish_frame,
        show_viewer=show_viewer,
        verbose=verbose,
    )
    return tracker, supervisor


@app.command()
def serve(
    scenario: str = typer.Argument(
        IDLE, help="Scenario to load at startup, or 'idle' to wait for the front end"
    ),
    host: Optional[str] = typer.Option(None, help="Address to bind"),
    port: Optional[int] = typer.Option(None, help="Port to bind"),
    scripts: bool = typer.Option(
        True, "--scripts/--no-scripts", help="Allow running user Python scripts"
    ),
    backend: Optional[str] = typer.Option(
        None, help="Physics backend: auto, gpu or cpu"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging"),
) -> None:
    """Run headless with the REST, WebSocket and video API. The default mode."""
    _configure_logging(verbose)

    settings = Settings.from_env()
    if backend is not None:
        settings.backend = backend
    if host is not None:
        settings.host = host
    if port is not None:
        settings.port = port
    settings.enable_script_api = scripts

    target = _resolve_scenario(scenario)
    _, supervisor = _build_stack(settings, show_viewer=False, verbose=verbose, with_api=True)

    raise typer.Exit(code=supervisor.run(target))


@app.command()
def viewer(
    scenario: str = typer.Argument(..., help="Scenario to open"),
    api: bool = typer.Option(
        False, "--api/--no-api", help="Also serve the API alongside the window"
    ),
    backend: Optional[str] = typer.Option(
        None, help="Physics backend: auto, gpu or cpu"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging"),
) -> None:
    """Open the native Genesis window on a scenario, for inspecting a scene."""
    _configure_logging(verbose)

    settings = Settings.from_env()
    settings.show_viewer = True
    if backend is not None:
        settings.backend = backend

    target = _resolve_scenario(scenario)
    if target == IDLE:
        typer.secho("viewer needs a scenario, not 'idle'.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    _, supervisor = _build_stack(settings, show_viewer=True, verbose=verbose, with_api=api)
    raise typer.Exit(code=supervisor.run(target))


@app.command()
def run(
    scenario: str = typer.Argument(..., help="Scenario to load"),
    script: Path = typer.Argument(..., help="Python script to execute against it"),
    backend: Optional[str] = typer.Option(
        None, help="Physics backend: auto, gpu or cpu"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging"),
) -> None:
    """Run a script against a scenario with no UI, exiting with its status code."""
    _configure_logging(verbose)

    script_path = script if script.is_absolute() else Path.cwd() / script
    if not script_path.exists():
        typer.secho(f"Script not found: {script_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    from src.api.script_runner import CLIENT_MISSING, client_available

    if not client_available():
        typer.secho(CLIENT_MISSING, fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    settings = Settings.from_env()
    if backend is not None:
        settings.backend = backend
    settings.host = "127.0.0.1"  # batch runs never expose the API
    settings.enable_script_api = False  # the script is driven from here instead

    target = _resolve_scenario(scenario)
    tracker, supervisor = _build_stack(
        settings, show_viewer=False, verbose=verbose, with_api=True
    )

    from src.runtime.script_run import run_script_against

    result = run_script_against(supervisor, tracker, script_path, settings.api_url)
    supervisor.run(target)
    raise typer.Exit(code=result["code"])


@app.command()
def validate(
    scenarios: Optional[list[str]] = typer.Argument(
        None, help="Scenario files to check. Defaults to every one in configs/scenarios"
    ),
) -> None:
    """Parse scenarios and check their assets, without starting Genesis."""
    from src.core.scenario import ScenarioError, discover_scenarios, load_scenario

    settings = Settings.from_env()
    targets = (
        [Path(s) for s in scenarios]
        if scenarios
        else discover_scenarios(settings.scenarios_dir)
    )

    if not targets:
        typer.secho(
            f"No scenarios found in {settings.scenarios_dir}",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1)

    failures = 0
    for target in targets:
        try:
            config = load_scenario(target)
        except ScenarioError as error:
            failures += 1
            typer.secho(f"FAIL  {error}", fg=typer.colors.RED, err=True)
            continue

        typer.secho(
            f"OK    {config.name}: {len(config.controllable_robots)} robot(s), "
            f"{len(config.objects)} object(s), {len(config.objectives)} objective(s)",
            fg=typer.colors.GREEN,
        )

    if failures:
        typer.secho(f"\n{failures} of {len(targets)} scenarios failed.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


def cli_entry_point() -> None:
    app()


if __name__ == "__main__":
    app()
