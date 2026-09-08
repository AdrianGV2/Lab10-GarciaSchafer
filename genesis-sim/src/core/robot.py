"""Robot controller and kinematics calculations."""

import numpy as np
import logging
from src.config import RobotConfig

logger = logging.getLogger(__name__)

def _to_numpy(data):
    if isinstance(data, np.ndarray): return data
    if isinstance(data, (list, tuple)): return np.asarray(data, dtype=float)
    if hasattr(data, "detach"): return data.detach().cpu().numpy()
    if hasattr(data, "cpu"): return data.cpu().numpy()
    return np.asarray(data, dtype=float)

def _complete_qpos(qpos_goal, qpos_reference):
    qpos_goal = _to_numpy(qpos_goal).astype(float)
    qpos_reference = _to_numpy(qpos_reference).astype(float)
    if qpos_goal.shape[0] >= qpos_reference.shape[0]: return qpos_goal
    full_qpos = qpos_reference.copy()
    full_qpos[: qpos_goal.shape[0]] = qpos_goal
    return full_qpos

def steps_calculation(joint_diff, velocity_rad_s=0.8, dt=0.01, verbose=False):
    max_rotation = np.max(joint_diff)
    duration_seconds = max_rotation / velocity_rad_s
    calculated_waypoints = int(duration_seconds / dt)
    num_waypoints = max(10, calculated_waypoints)
    return num_waypoints

def _wrap_to_pi(angle):
    return (angle + np.pi) % (2.0 * np.pi) - np.pi

def _scara_planar_ik_arm_controller(x_user, y_user, l1_m, l2_m, use_positive_s2=None):
    x_robot = y_user
    y_robot = -x_user
    c2 = float(np.clip((x_robot**2 + y_robot**2 - l1_m**2 - l2_m**2) / (2.0 * l1_m * l2_m), -1.0, 1.0))
    s2_magnitude = np.sqrt(max(0.0, 1.0 - c2**2))
    
    if use_positive_s2 is None: use_positive_s2 = x_user <= 0.0
    s2 = s2_magnitude if use_positive_s2 else -s2_magnitude

    theta2 = np.arctan2(s2, c2)
    k1 = l1_m + l2_m * np.cos(theta2)
    k2 = l2_m * np.sin(theta2)
    theta1 = np.arctan2(y_robot, x_robot) - np.arctan2(k2, k1)
    return float(theta1), float(theta2)

def movement(val_x, val_y, val_z, robot, end_effector, actual_qpos, actual_cartesian=None, quat_target=None,
            cartesian_speed=0.20, dt=0.01, keep_tool_down=True, rot_mask=None,
            ik_dofs_idx=None, preserve_dofs_idx=None, max_solver_iters=80,
            scara_l1=0.228, scara_l2=0.1365, scara_phi_target=0.0, scara_z_gain=1.0, scara_joint_speed=0.8,
            robot_base_pos=None):
    
    q_seed = _to_numpy(actual_qpos).astype(float)
    if actual_cartesian is not None:
        start_pos = _to_numpy(actual_cartesian).astype(float)
    else:
        start_pos = _to_numpy(end_effector.get_pos()).astype(float)

    base = np.array(robot_base_pos, dtype=float)[:3] if robot_base_pos is not None else np.zeros(3)
    
    target_local = np.array([val_x, val_y, val_z], dtype=float)
    target_pos = target_local + base
    start_local  = start_pos  - base

    if ik_dofs_idx is None or len(ik_dofs_idx) < 3:
        raise ValueError("ik_dofs_idx debe contener al menos 3 juntas: [J1, Z, J3, ...].")

    arm_dofs = np.asarray(ik_dofs_idx, dtype=int).reshape(-1)
    j1_idx, z_idx, j3_idx = arm_dofs[0], arm_dofs[1], arm_dofs[2]
    j4_idx = arm_dofs[3] if arm_dofs.size > 3 else None

    theta1_start, theta2_start = _scara_planar_ik_arm_controller(
        float(start_local[0]),  float(start_local[1]),  scara_l1, scara_l2)
    theta1_goal_pref, theta2_goal_pref = _scara_planar_ik_arm_controller(
        float(target_local[0]), float(target_local[1]), scara_l1, scara_l2,
        float(target_local[0]) <= 0.0)
    theta1_goal_alt, theta2_goal_alt = _scara_planar_ik_arm_controller(
        float(target_local[0]), float(target_local[1]), scara_l1, scara_l2,
        not (float(target_local[0]) <= 0.0))

    q_goal_pref, q_goal_alt = q_seed.copy(), q_seed.copy()
    q_goal_pref[j1_idx] = q_seed[j1_idx] + _wrap_to_pi(theta1_goal_pref - theta1_start)
    q_goal_pref[j3_idx] = q_seed[j3_idx] + _wrap_to_pi(theta2_goal_pref - theta2_start)
    q_goal_alt[j1_idx] = q_seed[j1_idx] + _wrap_to_pi(theta1_goal_alt - theta1_start)
    q_goal_alt[j3_idx] = q_seed[j3_idx] + _wrap_to_pi(theta2_goal_alt - theta2_start)

    q_goal = q_goal_pref
    q_goal[z_idx] = q_seed[z_idx] + float(scara_z_gain) * (target_local[2] - start_local[2])

    lower, upper = robot.get_dofs_limit()
    lower, upper = _to_numpy(lower).astype(float), _to_numpy(upper).astype(float)

    q_goal_pref[z_idx], q_goal_alt[z_idx] = q_goal[z_idx], q_goal[z_idx]

    def _branch_cost(q_candidate):
        over = np.maximum(q_candidate - upper, 0.0) + np.maximum(lower - q_candidate, 0.0)
        return 1e3 * float(np.sum(np.abs(over[arm_dofs]))) + float(np.sum(np.abs(q_candidate[arm_dofs] - q_seed[arm_dofs])))

    q_goal = q_goal_pref if _branch_cost(q_goal_pref) <= _branch_cost(q_goal_alt) else q_goal_alt
    q_goal = np.minimum(np.maximum(q_goal, lower), upper)

    try:
        q_goal_ik = robot.inverse_kinematics(
            link=end_effector, pos=target_pos, quat=None if quat_target is None else np.array(quat_target, dtype=float),
            init_qpos=q_goal, max_solver_iters=max_solver_iters, max_samples=1, max_step_size=0.1,
            pos_tol=1e-4, rot_tol=1e-3, rot_mask=[False, False, False], dofs_idx_local=arm_dofs,
        )
        q_goal = np.minimum(np.maximum(_complete_qpos(q_goal_ik, q_goal), lower), upper)
    except Exception as e:
        logger.warning(f"Fallo en Resolución de Cinemática Inversa: {e}. Evaluando clip de urgencia.")

    if preserve_dofs_idx is not None and len(preserve_dofs_idx) > 0:
        q_goal[preserve_dofs_idx] = q_seed[preserve_dofs_idx]

    joint_diff = np.abs(q_goal[arm_dofs] - q_seed[arm_dofs])
    num_waypoints = steps_calculation(joint_diff, float(scara_joint_speed), dt)

    path = []
    for alpha in np.linspace(1.0 / num_waypoints, 1.0, num_waypoints):
        q_step = q_seed + (q_goal - q_seed) * alpha
        if preserve_dofs_idx is not None and len(preserve_dofs_idx) > 0:
            q_step[preserve_dofs_idx] = q_seed[preserve_dofs_idx]
        path.append(q_step.copy())
    return path


class RobotController:
    def __init__(self, robot_entity, end_effector_name=None):
        self.robot = robot_entity
        ee_name = end_effector_name or RobotConfig.END_EFFECTOR_NAME
        self.end_effector = self.robot.get_link(ee_name)

        self.arm_dof = self._resolve_joint_dofs(RobotConfig.ARM_JOINT_NAMES)
        self.gripper_dof = self._resolve_joint_dofs(RobotConfig.GRIPPER_JOINT_NAMES)

        self.dof = np.arange(len(_to_numpy(self.robot.get_dofs_position())), dtype=int)

        self.robot.set_dofs_kp(np.full(len(self.dof), 4500.0), self.dof)
        self.robot.set_dofs_kv(np.full(len(self.dof), 450.0), self.dof)
        self.robot.set_dofs_force_range(
            np.full(len(self.dof), -100.0),
            np.full(len(self.dof), 100.0),
            self.dof
        )
        
        self.start_qpos = _to_numpy(self.robot.get_dofs_position()).astype(float).copy()
        
        self.actual_qpos = self.start_qpos.copy()
        self.home_qpos = self.start_qpos.copy()

        self.base_pos_world = _to_numpy(self.robot.get_pos()).astype(float).copy()
        
        self.is_grasping = False
        self.robot.control_dofs_position(self.actual_qpos, self.dof)
        
        self.ideal_cartesian = None

    def _resolve_joint_dofs(self, joint_names):
        dofs = []
        for name in joint_names:
            joint = self.robot.get_joint(name)
            dofs.extend(list(joint.dofs_idx_local))
        return np.asarray(dofs, dtype=int)

    @staticmethod
    def _fit_values(values, n):
        values = np.asarray(values, dtype=float).reshape(-1)
        if n == 0: return np.array([], dtype=float)
        if values.size == n: return values
        if values.size == 1: return np.full(n, values[0], dtype=float)
        if values.size > n: return values[:n]
        return np.concatenate([values, np.full(n - values.size, values[-1], dtype=float)])

    def _update_gripper_actuators(self):
        if self.gripper_dof.size == 0: return
        target = self._fit_values(RobotConfig.GRIPPER_CLOSED_QPOS if self.is_grasping else RobotConfig.GRIPPER_OPEN_QPOS, self.gripper_dof.size)
        self.actual_qpos[self.gripper_dof] = target
        self.robot.control_dofs_position(target, self.gripper_dof)

    def update_hardware_state(self, next_qpos=None):
        """Aplica el estado guardado a TODOS los motores en una sola orden."""
        
        if next_qpos is not None:
            qpos = _to_numpy(next_qpos).astype(float)
            self.actual_qpos[self.arm_dof] = qpos[self.arm_dof]
            
        if self.gripper_dof.size > 0:
            if self.is_grasping:
                target = self._fit_values(RobotConfig.GRIPPER_CLOSED_QPOS, self.gripper_dof.size)
            else:
                target = self._fit_values(RobotConfig.GRIPPER_OPEN_QPOS, self.gripper_dof.size)
            
            self.actual_qpos[self.gripper_dof] = target

        self.robot.control_dofs_position(self.actual_qpos, self.dof)

    def move_to(self, x, y, z):
        path = movement(
            val_x=x, val_y=y, val_z=z, robot=self.robot, end_effector=self.end_effector,
            actual_qpos=self.actual_qpos, actual_cartesian=self.ideal_cartesian,
            cartesian_speed=RobotConfig.DEFAULT_CARTESIAN_SPEED,
            ik_dofs_idx=self.arm_dof, preserve_dofs_idx=self.gripper_dof,
            max_solver_iters=RobotConfig.MAX_SOLVER_ITERS, scara_l1=RobotConfig.SCARA_L1,
            scara_l2=RobotConfig.SCARA_L2, scara_joint_speed=RobotConfig.SCARA_JOINT_SPEED,
            dt=1/60.0,
            robot_base_pos=self.base_pos_world,
        )
        
        # Guardado en coordenadas de MUNDO: movement() siempre resta
        # robot_base_pos de start_pos (ver start_local = start_pos - base),
        # tanto si start_pos viene de aca como si viene de end_effector.get_pos().
        # Guardarlo en local (como llegan x,y,z, ya relativos a la base) hacia
        # que esa resta se aplicara dos veces en cada move_to posterior al
        # primero, arrastrando el brazo a una posicion cada vez mas alejada
        # del objetivo real.
        self.ideal_cartesian = np.array([x, y, z], dtype=float) + self.base_pos_world

        return path

    def move_joints_fk(self, theta1_deg: float, z_cm: float, theta3_deg: float, theta4_deg: float = 0.0):
        """Dispara rotaciones absolutas simultáneas para los 4 joints del brazo."""
        q_goal = _to_numpy(self.actual_qpos).astype(float).copy()
        j1_idx = self.arm_dof[0]
        z_idx  = self.arm_dof[1]
        j3_idx = self.arm_dof[2]
        j4_idx = self.arm_dof[3] if len(self.arm_dof) > 3 else None

        q_goal[j1_idx] = float(np.deg2rad(theta1_deg))
        q_goal[z_idx]  = float(z_cm / 100.0)  # cm -> metros
        q_goal[j3_idx] = float(np.deg2rad(theta3_deg))
        if j4_idx is not None:
            q_goal[j4_idx] = float(np.deg2rad(theta4_deg))
        
        lower, upper = self.robot.get_dofs_limit()
        lower, upper = _to_numpy(lower).astype(float), _to_numpy(upper).astype(float)
        q_goal = np.minimum(np.maximum(q_goal, lower), upper)

        joint_diff = np.abs(q_goal[self.arm_dof] - self.actual_qpos[self.arm_dof])
        num_waypoints = steps_calculation(joint_diff, velocity_rad_s=RobotConfig.SCARA_JOINT_SPEED, dt=1/60.0)

        path = []
        for alpha in np.linspace(1.0 / num_waypoints, 1.0, num_waypoints):
            path.append(self.actual_qpos + (q_goal - self.actual_qpos) * alpha)
            
        self.ideal_cartesian = None
        return path

    def handle_fk_action(self, command: dict):
        """Desempaqueta las cargas de la API limpiamente para el caso FK"""
        meta = command.get("metadata", {}) or {}
        return self.move_joints_fk(
            theta1_deg=float(meta.get("j1", 0.0)),
            z_cm=float(meta.get("z", 0.0)),
            theta3_deg=float(meta.get("j3", 0.0)),
            theta4_deg=float(meta.get("j4", 0.0)),
        )

    def grasp(self): self.is_grasping = True
    def release(self): self.is_grasping = False
    
    def home(self):
        path = []
        for alpha in np.linspace(0, 1, 50):
            path.append(self.actual_qpos + (self.home_qpos - self.actual_qpos) * alpha)
        # move_to() usa ideal_cartesian como punto de partida cartesiano del
        # siguiente movimiento; si queda con el valor de antes del homing, el
        # primer move_to tras un home() calcula su interpolacion (incluido el
        # eje Z) desde una posicion que ya no es la real. None hace que vuelva
        # a leerse de end_effector.get_pos() una vez el homing termine.
        self.ideal_cartesian = None
        return path

    def reset_state(self):
        self.actual_qpos = self.home_qpos.copy()
        self.is_grasping = False
        self.robot.set_dofs_position(self.actual_qpos, self.dof)
        self.robot.control_dofs_position(self.actual_qpos, self.dof)

    def hibernate(self):
        """Forcefully freezes the active PID locks to prevent gravity collapse before detaching."""
        self.robot.control_dofs_position(self.actual_qpos, self.dof)

def global_scene_reset(scene, controllers_registry, active_robot_name):
    """Lleva a cabo la purga del Taichi Engine y el reanclaje masivo de cerrojos PD."""
    scene.reset()
    
    import numpy as np
    for name, rc in controllers_registry.items():
        nuevo_rc = RobotController(rc.robot)
        nuevo_rc.start_qpos = np.zeros_like(nuevo_rc.start_qpos)
        nuevo_rc.actual_qpos = nuevo_rc.start_qpos.copy()
        nuevo_rc.home_qpos = nuevo_rc.start_qpos.copy()
        nuevo_rc.ideal_cartesian = None
        
        controllers_registry[name] = nuevo_rc
        if name != active_robot_name:
            nuevo_rc.hibernate()
            
    active_bot = controllers_registry[active_robot_name]
    active_bot.reset_state()
    return controllers_registry, active_bot

def switch_active_robot(command: dict, controllers_registry: dict, current_robot: RobotController):
    """Encapsula la validación de Hot-Swap transfiriendo las fuerzas lógicas PID."""
    target_name = command.get("robot_name")
    if not target_name:
        meta = command.get("metadata", {}) or {}
        target_name = meta.get("robot_name")
    
    if target_name in controllers_registry:
        logger.info(f"Cambiando posesión de IA hacia: {target_name}")
        current_robot.hibernate()
        
        new_robot = controllers_registry[target_name]
        new_robot.ideal_cartesian = None
        
        return target_name, new_robot, True
    
    logger.error(f"El robot solicitado '{target_name}' no existe en el registro.")
    return None, current_robot, False