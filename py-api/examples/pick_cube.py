"""Pick up the green cube and lift it, three times over.

Runs against the simulator or the real arm; only the host and port change.
"""

import typer

from manito_api import ManitoArm


def main(host: str = "localhost", port: int = 8080):
    arm = ManitoArm(f"http://{host}:{port}")
    arm.home()

    for i in range(3):
        arm.move_joints(0, 90, 0, 20)   # reach down to the cube
        arm.gripper(True)               # close
        arm.move_joints(0, 0, 0, 20)    # lift
        arm.gripper(False)              # release
        print("Cycle", i + 1, "done")

    arm.home()


if __name__ == "__main__":
    typer.run(main)
