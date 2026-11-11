"""Base class for all world entities (player, zombies, bullets, pickups)."""
from __future__ import annotations

from typing import Tuple

from engine.collision import distance2


class Entity:
    """A world-space object with a position, radius and simple HP."""

    def __init__(self, x: float, y: float, radius: float = 0.4,
                 z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.radius = radius
        self.hp = 0.0
        self.max_hp = 0.0
        self.alive = True
        self.kind: str = "entity"

    # ------------------------------------------------------------------
    @property
    def pos(self) -> Tuple[float, float]:
        return self.x, self.y

    @property
    def depth(self) -> float:
        """Iso depth-sort key (see engine.iso)."""
        return self.x + self.y

    def dist2(self, other) -> float:
        return distance2(self.x, self.y, other.x, other.y) \
            if isinstance(other, Entity) else \
            distance2(self.x, self.y, other[0], other[1])

    def dist(self, other) -> float:
        import math
        return math.sqrt(self.dist2(other))

    def overlap(self, other, pad: float = 0.0) -> bool:
        r = self.radius + other.radius + pad
        d = self.dist2(other)
        return d < r * r

    def update(self, dt: float) -> None:  # pragma: no cover - override
        pass

    def on_hit(self, dmg: float, src) -> None:
        self.hp -= dmg
        if self.hp <= 0:
            self.alive = False
