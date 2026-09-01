"""Camera controller for spherical navigation around the Genesis simulation."""

import math
import logging

logger = logging.getLogger(__name__)

class CameraController:
    def __init__(self, cam):
        self.cam = cam
        
        current_pos = list(cam.pos)
        self._lookat = list(cam.lookat)
        
        dx = current_pos[0] - self._lookat[0]
        dy = current_pos[1] - self._lookat[1]
        dz = current_pos[2] - self._lookat[2]
        
        self.radius = math.sqrt(dx**2 + dy**2 + dz**2)
        
        if self.radius == 0:
            self.radius = 0.1
        
        self.azimuth = math.atan2(dy, dx)
        
        self.elevation = math.asin(dz / self.radius)
        
        self.MIN_RADIUS = 0.5
        self.MAX_RADIUS = 5.0
        self.MIN_ELEVATION = math.radians(5)
        self.MAX_ELEVATION = math.radians(85)
        
    def _euler_to_quat(self, roll, pitch, yaw):
        """Convierte angulos de Euler a matriz Quaternion (w, x, y, z)"""
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return (w, x, y, z)
        
    def _apply(self):
        """Traduce las coordenadas esfericas a matriz cartesiana y fuerza la rotación rígida."""
        x = self._lookat[0] + self.radius * math.cos(self.elevation) * math.cos(self.azimuth)
        y = self._lookat[1] + self.radius * math.cos(self.elevation) * math.sin(self.azimuth)
        z = self._lookat[2] + self.radius * math.sin(self.elevation)
        new_pos = (x, y, z)
        try:
            self.cam.set_pose(pos=new_pos, lookat=self._lookat, up=(0.0, 0.0, 1.0))
        except Exception as e:
            logger.error(f"Falla crítica moviendo cámara en Fase 4 vector up: {e}")
            
    def zoom(self, delta: float):
        """Un delta local (+0.2) acorta la distancia."""
        if delta == 0.0: return
        self.radius = max(self.MIN_RADIUS, min(self.MAX_RADIUS, self.radius - delta))
        self._apply()

    def elevate(self, delta: float):
        """Mueve la camara resbalandola verticalmente por la cupula."""
        if delta == 0.0: return
        self.elevation = max(self.MIN_ELEVATION, min(self.MAX_ELEVATION, self.elevation + delta))
        self._apply()
        
    def pan(self, delta: float):
        """Orbita el azimuth para rodear 360 al robot en el plano horizontal."""
        if delta == 0.0: return
        self.azimuth = (self.azimuth + delta) % (2.0 * math.pi)
        self._apply()
