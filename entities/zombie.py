"""Zombie entity: per-type stats, animation and movement state.

The behaviour (detect / pursue / navigate / attack) lives in
:mod:`systems.enemy_ai`; this class owns the data the AI reads and writes.
"""
from __future__ import annotations

import config
from entities.entity_base import Entity


class Zombie(Entity):
    def __init__(self, x: float, y: float, ztype: str = "regular") -> None:
        spec = config.ZOMBIE_TYPES[ztype]
        super().__init__(x, y, radius=spec["radius"], z=0.0)
        self.kind = f"zombie_{ztype}"
        self.ztype = ztype
        self.spec = spec
        self.max_hp = spec["hp"]
        self.hp = spec["hp"]
        self.speed = spec["speed"]
        self.damage = spec["damage"]
        self.detect = spec["detect"]
        self.attack_range = spec["range"]
        self.attack_cd = spec["attack_cd"]
        self.score = spec["score"]

        self.state = "idle"          # idle | pursue | attack
        self._attack_timer = 0.0
        self.moving = False
        self.anim_state = "idle"
        self.anim_timer = 0.0
        self.frame_index = 0
        self.hit_flash = 0.0

        # AI / navigation
        self.wander_target = None
        self.wander_timer = 0.0
        self.path = None
        self.path_i = 0
        self.repath_timer = 0.0
        self.facing = 1.0
        self.groan_timer = 0.0

    # ------------------------------------------------------------------
    @property
    def pos(self):
        return self.x, self.y

    @property
    def depth(self):
        return self.x + self.y

    def apply_move(self, vx: float, vy: float, dt: float, grid) -> None:
        if abs(vx) < 1e-5 and abs(vy) < 1e-5:
            self.moving = False
            return
        import math
        m = math.hypot(vx, vy) or 1.0
        dx = vx / m * self.speed * dt
        dy = vy / m * self.speed * dt
        self.x, self.y = grid.move_circle((self.x, self.y), (dx, dy),
                                           self.radius)
        self.moving = True
        # facing flips on the screen-horizontal axis of movement
        self.facing = -1.0 if (vx - vy) < 0 else 1.0

    # ------------------------------------------------------------------
    def on_hit(self, dmg: float, src) -> None:
        self.hp -= dmg
        self.hit_flash = 0.12
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.anim_state = "dead"

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Animation + timers (AI decisions are made by enemy_ai)."""
        self._attack_timer = max(0.0, self._attack_timer - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.anim_timer += dt
        if self.alive and self.hit_flash > 0:
            self.anim_state = "hit"
        elif self.alive and self.moving:
            self.anim_state = "walk"
        elif self.alive and self.state == "attack":
            self.anim_state = "attack"
        elif self.alive:
            self.anim_state = "idle"
        rate = 6.0 if self.anim_state == "walk" else 4.0
        self.frame_index = int(self.anim_timer * rate) % 2

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "ztype": self.ztype,
                "hp": self.hp}
