"""The FastAPI application and the thread it runs in.

Shared objects live on `app.state` rather than in per-module globals, so the
app can be built more than once (tests, batch runs) and every route reaches the
same settings, queue and tracker through the request.
"""

import logging
import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.middlewares import setup_middlewares
from src.api.routes_driver import router as driver_router
from src.api.routes_robot import router as robot_router
from src.api.routes_scenarios import router as scenarios_router
from src.api.routes_script import router as script_router
from src.api.routes_video import VideoStream
from src.api.routes_video import router as video_router
from src.api.routes_ws import router as ws_router
from src.api.script_runner import ScriptRunner, client_available
from src.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)


def create_app(settings, command_queue, tracker) -> FastAPI:
    app = FastAPI(title="Manito Genesis Simulator")
    setup_middlewares(app)

    app.state.settings = settings
    app.state.command_queue = command_queue
    app.state.tracker = tracker
    app.state.video = VideoStream()

    if settings.enable_script_api:
        app.state.script_runner = ScriptRunner(settings.script_dir, settings.api_url)
        if not client_available():
            logger.warning(
                "'manito-api' is not installed: the editor's Python tab and "
                "`simctl run` will report an error until you run "
                "`uv sync --extra scripts`."
            )
    else:
        app.state.script_runner = None

    for router in (
        robot_router,
        ws_router,
        video_router,
        scenarios_router,
        driver_router,
        script_router,
    ):
        app.include_router(router)

    # Serve the built front end from the API when it exists, so the whole thing
    # runs on one port and the browser talks to its own origin. Mounted last:
    # a mount at "/" matches any path the API routes above did not claim.
    frontend_dist = PROJECT_ROOT / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
        logger.info("Serving the front end from %s", frontend_dist)

    return app


def start_api_server(settings, command_queue, tracker) -> tuple:
    """Start uvicorn on a daemon thread. Returns (thread, app)."""
    import uvicorn

    app = create_app(settings, command_queue, tracker)

    if settings.binds_publicly and settings.enable_script_api:
        logger.warning(
            "Serving on %s with script execution enabled: anyone who can reach "
            "this port can run arbitrary Python on this machine. Use a trusted "
            "network, or start with --no-scripts.",
            settings.host,
        )

    def serve():
        import asyncio

        config = uvicorn.Config(
            app=app,
            host=settings.host,
            port=settings.port,
            log_level="info",
            access_log=False,
        )
        asyncio.run(uvicorn.Server(config).serve())

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return thread, app


__all__ = ["create_app", "start_api_server"]
