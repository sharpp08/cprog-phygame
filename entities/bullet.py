"""A travelling projectile in world space.

Bullets are fired toward a *world-space* aim point (never raw screen
coordinates) so they travel correctly on the isometric ground plane.
"""
from __future__ import annotations

import math
import random
from typing import Tuple


class Bullet:
    def __init__(self, x: float, y: float, direction: Tuple[float, float],
                 speed: float, damage: float, rng: float, color,
                 pellets: int = 1, spread: float = 0.0,
                 z: float = 0.35) -> None:
        d = math.hypot(direction[0], direction[1]) or 1.0
        dx, dy = direction[0] / d, direction[1] / d
        if pellets > 1:
            ang = random.gauss(0.0, max(spread, 0.05))
            ca, sa = math.cos(ang), math.sin(ang)
            dx, dy = dx * ca - dy * sa, dx * sa + dy * ca
        self.x, self.y, self.z = float(x), float(y), z
        self.dx, self.dy = dx, dy
        self.speed = speed
        self.damage = damage
        self.max_dist = rng
        self.trav = 0.0
        self.active = True
        self.color = color
        self.pellets = pellets
        self.hit_zombie = None

    def update(self, dt: float) -> None:
        step = self.speed * dt
        self.x += self.dx * step
        self.y += self.dy * step
        self.trav += step
        if self.trav >= self.max_dist:
            self.active = False

    def forward(self) -> Tuple[float, float]:
        return self.dx, self.dy
