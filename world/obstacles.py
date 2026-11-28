"""Obstacle records: trees, rocks, bushes, the shrine, waterfall and ruin."""
from __future__ import annotations

import config


class Obstacle:
    __slots__ = ("x", "y", "kind", "variant", "z", "solid", "scale", "collision_radius")

    def __init__(self, x: int, y: int, kind: str, variant: int = 0,
                 z: float = 0.0, solid: bool = True,
                 scale: float = 1.0, collision_radius: float = 0.34) -> None:
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.variant = variant
        self.z = z
        self.solid = solid
        self.scale = max(0.55, min(1.5, float(scale)))
        self.collision_radius = max(0.2, min(0.48, float(collision_radius)))

    @property
    def depth(self) -> float:
        return self.x + self.y

    @classmethod
    def from_dict(cls, d: dict) -> "Obstacle":
        return cls(d["x"], d["y"], d["kind"], d.get("variant", 0),
                   d.get("z", 0.0), d.get("solid", True),
                   d.get("scale", 1.0), d.get("collision_radius", 0.34))

    def in_rect(self, minx, miny, maxx, maxy, pad: float = 1.0) -> bool:
        return (self.x >= minx - pad and self.x <= maxx + pad and
                self.y >= miny - pad and self.y <= maxy + pad)

    # kind -> base sprite / anchor info used by the renderer
    @property
    def tall(self) -> bool:
        return self.kind in ("tree", "shrine", "waterfall", "ruin")
