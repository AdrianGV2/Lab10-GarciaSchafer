"""Configuration settings for the robot hardware and simulation."""

class RobotConfig:
    # 1. Joints Brazo
    ARM_JOINT_NAMES = ["Joint_1", "Joint_2", "Joint_3", "Joint_4"]
    
    # 2. Joits Garra
    GRIPPER_JOINT_NAMES = ["Joint_5", "Joint_6"]
    
    # 3. End Effector
    END_EFFECTOR_NAME = "Link_5" 
    
    # 4. Configuración de la garra
    GRIPPER_OPEN_QPOS = [0.0, 0.0]
    GRIPPER_CLOSED_QPOS = [0.025, -0.025]
    
    # 5. Parametros de movimiento y cinemática
    SCARA_L1 = 0.228 
    SCARA_L2 = 0.1365
    
    # Comportamiento
    SCARA_PHI_TARGET = 0.0 
    SCARA_Z_GAIN = 1.0
    SCARA_JOINT_SPEED = 0.8 
    DEFAULT_CARTESIAN_SPEED = 0.20
    MAX_SOLVER_ITERS = 80
    
    EE_QUAT_TARGET = None
    IK_ROT_MASK = [False, False, False]