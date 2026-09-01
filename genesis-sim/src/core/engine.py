"""The Genesis physics loop.

Runs inside the simulation worker process, which is the only place Genesis is
ever initialised. The loop advances the scene at a fixed timestep and hands
control to a callback after each step, so command handling, telemetry and
video capture all happen between frames rather than on another thread.
"""

from typing import Optional, Any
import logging

try:
    import genesis as gs
    _GENESIS_AVAILABLE = True
except ImportError:
    _GENESIS_AVAILABLE = False


logger = logging.getLogger(__name__)

class ReloadScenarioException(Exception):
    """Excepción controlada para forzar el reinicio de la escena física (Hot-Swap)."""
    def __init__(self, scenario_path: str):
        self.scenario_path = scenario_path
        super().__init__(f"Reloading scenario: {scenario_path}")



def run(
    scene: gs.Scene,
    step_callback: callable,
    max_steps: Optional[int] = None,
    cam: Optional[Any] = None,
) -> None:
    """Advance the scene at 60 Hz, calling back after every step.

    Args:
        scene: A built Genesis scene.
        step_callback: Called as ``step_callback(step_count, scene)`` after each
            ``scene.step()``.
        max_steps: Stop after this many steps. Runs until interrupted if None.
        cam: The streaming camera, kept for callers that render from the loop.

    Raises:
        RuntimeError: If Genesis is not installed, or the loop fails.
        ReloadScenarioException: Propagated so the worker can exit for a
            scenario hot-swap.
    """
    if not _GENESIS_AVAILABLE:
        raise RuntimeError(
            "Genesis is not installed. Install via: uv add 'genesis @ git+https://github.com/Genesis-Embodied-AI/Genesis.git'"
        )

    if not callable(step_callback):
        raise TypeError("step_callback must be a callable")

    try:
        logger.info("Starting simulation loop...")

        import time
        
        step_count = 0
        dt_physics = 1/60.0
        
        while True:
            start_time = time.perf_counter()
            
            if max_steps is not None and step_count >= max_steps:
                logger.info(f"Reached maximum step limit ({max_steps} steps). Exiting.")
                break

            scene.step()
                
            try:
                step_callback(step_count, scene)
            except ReloadScenarioException:
                raise
            except Exception as callback_error:
                logger.error(f"Error in step callback: {callback_error}")
                raise

            step_count += 1

            if step_count % 100 == 0:
                logger.debug(f"Simulation step: {step_count}")

            elapsed = time.perf_counter() - start_time
            if elapsed < dt_physics:
                time.sleep(dt_physics - elapsed)

    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user (Ctrl+C)")
        try:
            scene.viewer.close()
        except Exception:
            pass
    except ReloadScenarioException:
        logger.info("Simulation loop broken for scenario reload.")
        raise
    except Exception as e:
        raise RuntimeError(f"Error during simulation execution with callbacks: {e}") from e
    finally:
        logger.info(f"Simulation terminated after {step_count} steps")
