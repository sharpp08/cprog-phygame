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
        # Smoothed speed / movement amount so walk<->run<->idle blends.
        self._move_amt = 0.0        # 0 (idle)..1 (full run)
        self._cur_speed = config.PLAYER_WALK_SPEED

        self.invuln = 0.0
        self.damage_timer = 0.0
        self.dmg_flash = 0.0
        self._shoot_flash = 0.0

        self.anim_state = "idle"
        self.anim_timer = 0.0
        self.frame_index = 0
        # Gait phase drives the 4-frame walk/run cycle (0..1, wraps).
        self._gait = 0.0
        # Footstep cadence: which foot hits next + stride accumulator.
        self._foot = 0.0
        self._stride = 0.0
        self._step_side = 0
        self.footstep_sound = False
        self._last_footstep_state = 0
        self._bob = 0.0

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
        # Smoothly ease the effective movement amount 0->1 so starting and
        # stopping do not snap; this drives speed, gait rate and bob.
        target = 1.0 if self.running else (0.55 if self.moving else 0.0)
        k = min(1.0, dt * 7.0)
        self._move_amt += (target - self._move_amt) * k
        self._cur_speed = (config.PLAYER_WALK_SPEED *
                           (0.6 + 0.4 * self._move_amt) +
                           (config.PLAYER_RUN_SPEED - config.PLAYER_WALK_SPEED)
                           * max(0.0, self._move_amt - 0.55) / 0.45)
        if self.moving:
            # Normalise the move vector so diagonal speed is constant.
            m = (mv[0] ** 2 + mv[1] ** 2) ** 0.5 or 1.0
            dx = (mv[0] / m) * self._cur_speed * dt
            dy = (mv[1] / m) * self._cur_speed * dt
            self.x, self.y = grid.move_circle(
                (self.x, self.y), (dx, dy), self.radius)
            # Advance the gait cycle in proportion to distance travelled.
            self._gait += dt * self._cur_speed * 0.85
            if self._gait > 1.0:
                self._gait -= 1.0
            # Footstep cadence: a step on each half-stride, alternating feet.
            self._stride += dt * self._cur_speed * 0.5
            if self._stride >= 0.5:
                self._stride -= 0.5
                self._step_side = 1 - self._step_side
                self.footstep_sound = True
                self._last_footstep_state = 1
        else:
            # Decelerate: keep a short glide, then settle to idle.
            self._stride = 0.0
            self.footstep_sound = False
            self._last_footstep_state = 0

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

        # Animation state machine: prioritise hurt > reload > shoot > move.
        if self.damage_timer > 0:
            self.anim_state = "hit"
        elif self.weapon.reloading:
            self.anim_state = "reload"
        elif self._shoot_flash > 0:
            self.anim_state = "shoot"
        elif self._move_amt > 0.7:
            self.anim_state = "run"
        elif self._move_amt > 0.15:
            self.anim_state = "walk"
        else:
            self.anim_state = "idle"

        # Body bob driven by the gait cycle (highest mid-stride).
        import math
        if self.anim_state in ("walk", "run"):
            self._bob = abs(math.sin(self._gait * math.pi)) \
                * (2.0 if self.anim_state == "walk" else 4.0)
        else:
            self._bob = 0.0

        # Pick the gait frame.  Walk/run use the 4-frame cycle indexed by
        # the gait phase; idle gently breathes through the idle frames.
        if self.anim_state in ("walk", "run"):
            self.frame_index = int(self._gait * 4) % 4
        elif self.anim_state == "idle":
            self.anim_timer += dt
            self.frame_index = int(self.anim_timer * 1.5) % 4
        elif self.anim_state == "reload":
            self.anim_timer += dt
            self.frame_index = int(self.anim_timer * 3.0) % 4
        else:
            self.frame_index = 0

    @property
    def bob(self) -> float:
        """Vertical body offset (px) for the renderer to lift the sprite."""
        return getattr(self, "_bob", 0.0)

    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y, "hp": self.hp,
            "weapons": [w.to_dict() for w in self.weapons],
            "current": self.current,
        }
