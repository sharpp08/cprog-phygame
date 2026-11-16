"""Continuous, camera-independent world-space cloud simulation.

Cloud coordinates are unbounded world coordinates.  They are never wrapped
at map edges; distant clouds are recycled outside the view around the camera.
This module deliberately has no Pygame dependency so it can be tested headlessly.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass
class Cloud:
    x: float
    y: float
    height: float
    scale: float
    vx: float
    vy: float
    phase: float
    texture: int
    wind_response: float


class CloudField:
    def __init__(self, count: int = 28, seed: int = 49271) -> None:
        self.count = max(1, int(count))
        self.rng = random.Random(seed)
        self.clouds: list[Cloud] = []
        self.wind_x = 0.0
        self.wind_y = 0.0
        self._initialized = False

    def _make_cloud(self, x: float, y: float) -> Cloud:
        angle = self.rng.uniform(-0.22, 0.22)
        speed = self.rng.uniform(0.28, 0.62)
        return Cloud(
            x=x, y=y,
            height=self.rng.uniform(5.5, 9.0),
            scale=self.rng.uniform(0.72, 1.5),
            vx=math.cos(angle) * speed,
            vy=math.sin(angle) * speed,
            phase=self.rng.uniform(0.0, math.tau),
            texture=self.rng.randrange(10),
            wind_response=self.rng.uniform(0.85, 1.15),
        )

    def initialize(self, camera_x: float, camera_y: float) -> None:
        """Seed a broad sky field around the current camera focus."""
        self.clouds.clear()
        for _ in range(self.count):
            self.clouds.append(self._make_cloud(
                camera_x + self.rng.uniform(-42.0, 42.0),
                camera_y + self.rng.uniform(-42.0, 42.0)))
        self._initialized = True

    def update(self, dt: float, camera_x: float, camera_y: float,
               wind: float = 0.0, wind_dir: float = 1.0) -> None:
        if dt <= 0.0:
            return
        if not self._initialized:
            self.initialize(camera_x, camera_y)

        target_x = float(wind) * math.cos(float(wind_dir))
        target_y = float(wind) * math.sin(float(wind_dir))
        blend = min(1.0, dt * 0.12)
        self.wind_x += (target_x - self.wind_x) * blend
        self.wind_y += (target_y - self.wind_y) * blend

        for cloud in self.clouds:
            response = cloud.wind_response
            cloud.x += (cloud.vx + self.wind_x * 0.32 * response) * dt
            cloud.y += (cloud.vy + self.wind_y * 0.32 * response) * dt

            # Recycle only when far outside the camera's world-space region.
            # The new position is on the far side of the sky, never at a map
            # edge and never inside the visible area.
            dx = cloud.x - camera_x
            dy = cloud.y - camera_y
            if dx * dx + dy * dy > 72.0 * 72.0:
                angle = math.atan2(self.wind_y, self.wind_x)
                if abs(self.wind_x) + abs(self.wind_y) < 0.03:
                    angle = 0.0
                angle += self.rng.uniform(-0.75, 0.75)
                radius = self.rng.uniform(76.0, 88.0)
                cloud.x = camera_x + math.cos(angle) * radius
                cloud.y = camera_y + math.sin(angle) * radius
