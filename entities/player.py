"""The player character: movement, aiming and weapon/animation state."""
from __future__ import annotations

from typing import List, Optional, Tuple

import config
from entities.entity_base import Entity
from entities.weapon import Weapon


class Player(Entity):
    def __init__(self, x: float, y: float,
                 weapons: Optional[List[Weapon]] = None) -> None:
        super().__init__(x, y, radius=config.PLAYER_RADIUS, z=0.0)
        self.kind = "player"
        self.hp = config.PLAYER_MAX_HP
        self.max_hp = config.PLAYER_MAX_HP
        self.weapons = weapons if weapons else [Weapon("pistol")]
        if "pistol" not in [w.kind for w in self.weapons]:
            self.weapons.insert(0, Weapon("pistol"))
        self.current = 0

        self.aim: Tuple[float, float] = (0.0, 0.0)
        self.facing = 1.0
        self.speed = config.PLAYER_WALK_SPEED
        self.moving = False
        self.running = False

        self.invuln = 0.0
        self.damage_timer = 0.0
        self.dmg_flash = 0.0
        self._shoot_flash = 0.0

        self.anim_state = "idle"
        self.anim_timer = 0.0
        self.frame_index = 0
        self._foot = 0.0
        self.footstep_sound = False

    # ------------------------------------------------------------------
    @property
    def weapon(self) -> Weapon:
        return self.weapons[self.current]

    @property
    def dead(self) -> bool:
        return self.hp <= 0

    def select_weapon(self, index: int) -> None:
        self.current = index % len(self.weapons)

    def has_weapon(self, kind: str) -> bool:
        return any(w.kind == kind for w in self.weapons)

    def add_weapon(self, w: Weapon) -> None:
        if not self.has_weapon(w.kind):
            self.weapons.append(w)
            self.current = len(self.weapons) - 1

    # ------------------------------------------------------------------
    def set_aim(self, dirx: float, diry: float) -> None:
        self.aim = (dirx, diry)
        self.facing = -1.0 if dirx < 0 else 1.0

    def apply_movement(self, mv: Tuple[float, float], running: bool,
                       dt: float, grid) -> None:
        self.moving = (mv[0] != 0.0 or mv[1] != 0.0)
        self.running = running and self.moving
        self.speed = (config.PLAYER_RUN_SPEED if self.running
                      else config.PLAYER_WALK_SPEED)
        if self.moving:
            dx = mv[0] * self.speed * dt
            dy = mv[1] * self.speed * dt
            self.x, self.y = grid.move_circle(
                (self.x, self.y), (dx, dy), self.radius)
            self._foot += dt * (self.speed * 0.55)
            if self._foot > 0.5:
                self._foot = 0.0
                self.footstep_sound = True
        else:
            self._foot = 0.0
            self.footstep_sound = False

    # ------------------------------------------------------------------
    def mark_shoot(self) -> None:
        self._shoot_flash = 0.12

    def take_damage(self, dmg: float) -> None:
        if self.invuln > 0 or self.dead:
            return
        self.hp = max(0.0, self.hp - dmg)
        self.damage_timer = 0.25
        self.dmg_flash = 0.5
        self.invuln = config.PLAYER_INVULN

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.dead:
            self.alive = False
            self.anim_state = "dead"
            return
        self.invuln = max(0.0, self.invuln - dt)
        self.damage_timer = max(0.0, self.damage_timer - dt)
        self.dmg_flash = max(0.0, self.dmg_flash - dt)
        self._shoot_flash = max(0.0, self._shoot_flash - dt)
        self.weapon.update(dt)

        if self.damage_timer > 0:
            self.anim_state = "hit"
        elif self.weapon.reloading:
            self.anim_state = "reload"
        elif self._shoot_flash > 0:
            self.anim_state = "shoot"
        elif self.moving:
            self.anim_state = "run" if self.running else "walk"
        else:
            self.anim_state = "idle"

        self.anim_timer += dt
        rate = 9.0 if self.anim_state in ("walk", "run") else 6.0
        self.frame_index = int(self.anim_timer * rate) % 2

    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y, "hp": self.hp,
            "weapons": [w.to_dict() for w in self.weapons],
            "current": self.current,
        }
