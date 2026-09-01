"""Catalog of the scenarios the front end can offer."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Request

from src.core.scenario import ScenarioError, discover_scenarios, load_scenario

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["scenarios"])


@router.get("/scenarios")
def get_scenarios(request: Request) -> Dict[str, Any]:
    """Every scenario in the configured directory, with its objectives."""
    scenarios = []

    for path in discover_scenarios(request.app.state.settings.scenarios_dir):
        try:
            config = load_scenario(path)
        except ScenarioError as error:
            logger.error("Skipping %s: %s", path.name, error)
            continue

        robots = config.controllable_robots
        scenarios.append(
            {
                "filename": config.name,
                "path": str(path),
                "objectives": config.objectives,
                "custom_blocks": config.custom_blocks,
                "robot_count": len(robots),
                "robot_names": [
                    robot.get("name", f"robot_{i}") for i, robot in enumerate(robots)
                ],
                "object_count": len(config.objects),
            }
        )

    return {"status": "success", "count": len(scenarios), "scenarios": scenarios}
