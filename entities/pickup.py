"""Collectible items on the ground: ammo, medkits, weapon crates."""
from __future__ import annotations

import config
from entities.entity_base import Entity


class Pickup(Entity):
    def __init__(self, x: float, y: float, ptype: str) -> None:
        super().__init__(x, y, radius=0.45)
        self.ptype = ptype
        self.spec = config.PICKUP_TYPES[ptype]
        self.value = self.spec["value"]
        self.bob = 0.0
        self.kind = "pickup"
        self.taken = False

    def update(self, dt: float) -> None:
        self.bob += dt
