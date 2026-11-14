"""The player character: movement, aiming and weapon/animation state."""
from __future__ import annotations

import math
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
        self._facing_target = 1.0
        self.speed = config.PLAYER_WALK_SPEED
        self.moving = False
        self.running = False
        self.crouching = False
        # Velocity is eased independently on each axis. Animation is driven by
        # measured post-collision displacement, never requested input, which
        # prevents feet cycling while pressed against geometry.
        self._velocity = (0.0, 0.0)
        self.actual_speed = 0.0
        self._move_amt = 0.0        # 0 (idle)..1 (full run)
        self._cur_speed = 0.0

        self.invuln = 0.0
        self.damage_timer = 0.0
        self.dmg_flash = 0.0
        self._shoot_flash = 0.0

        self.anim_state = "idle"
        self.prev_anim_state = "idle"
        self.prev_frame_index = 0
        self.anim_blend = 1.0
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
        if abs(dirx) > 0.04:
            self._facing_target = -1.0 if dirx < 0 else 1.0
        # Facing is eased in update() so aim changes do not snap the sprite.

    def apply_movement(self, mv: Tuple[float, float], running: bool,
                       dt: float, grid, speed_scale: float = 1.0) -> None:
        """Accelerated movement; gait follows measured displacement.

        Velocity is eased toward the requested input so starting, stopping
        and turning feel natural instead of snapping.  The gait phase and
        footstep cadence advance from the actual post-collision distance
        travelled, which prevents foot sliding while blocked by geometry.
        """
        dt = max(0.0, min(float(dt), 0.1))
        requested = abs(mv[0]) + abs(mv[1]) > 1e-6
        target_speed = (config.PLAYER_RUN_SPEED if running
                        else config.PLAYER_WALK_SPEED) * max(0.2, min(1.0, speed_scale))
        if requested:
            mag = math.hypot(mv[0], mv[1]) or 1.0
            target_vx = mv[0] / mag * target_speed
            target_vy = mv[1] / mag * target_speed
        else:
            target_vx = target_vy = 0.0

        vx, vy = self._velocity
        response = 16.0 if requested else 22.0
        blend = 1.0 - math.exp(-response * dt)
        vx += (target_vx - vx) * blend
        vy += (target_vy - vy) * blend
        if not requested and math.hypot(vx, vy) < 0.04:
            vx = vy = 0.0
        self._velocity = (vx, vy)

        old_x, old_y = self.x, self.y
        self.x, self.y = grid.move_circle(
            (old_x, old_y), (vx * dt, vy * dt), self.radius)
        travelled = math.hypot(self.x - old_x, self.y - old_y)
        self.actual_speed = travelled / dt if dt > 0.0 else 0.0
        self._cur_speed = self.actual_speed
        self.moving = self.actual_speed > 0.05
        self.running = (running and self.moving and
                        self.actual_speed > config.PLAYER_WALK_SPEED * 1.05)
        target_amt = min(1.0, self.actual_speed / config.PLAYER_RUN_SPEED)
        self._move_amt += (target_amt - self._move_amt) * blend

        if travelled > 1e-6:
            # Gait phase follows actual displacement, with a longer sprint
            # stride and shorter walking stride to prevent foot sliding.
            # Match the backward sweep of the planted foot to the distance
            # travelled during half a gait cycle.  Running has a longer stride
            # (lower cycles per tile); walking uses shorter, quicker steps.
            gait_rate = 0.44 if self.running else 0.81
            self._gait = (self._gait + travelled * gait_rate) % 1.0
            self._stride += travelled
            step_length = 1.14 if self.running else 0.62
            if self._stride >= step_length:
                self._stride %= step_length
                self._step_side = 1 - self._step_side
                self.footstep_sound = True
                self._last_footstep_state = 1
        elif not requested:
            # Decelerate: keep a short glide, then settle to idle.
            self._stride = 0.0
            self.footstep_sound = False
            self._last_footstep_state = 0

    # ------------------------------------------------------------------
    def mark_shoot(self) -> None:
        self._shoot_flash = 0.12
        self.anim_timer = 0.0

    def _set_anim_state(self, state: str) -> None:
        if state == self.anim_state:
            return
        self.prev_anim_state = self.anim_state
        self.prev_frame_index = self.frame_index
        self.anim_state = state
        self.anim_timer = 0.0
        self.anim_blend = 0.0

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
        # Smoothly rotate the sprite toward aim; this is frame-rate independent.
        facing_blend = 1.0 - math.exp(-18.0 * max(0.0, dt))
        self.facing += (self._facing_target - self.facing) * facing_blend

        # Animation state machine: prioritise hurt > reload > shoot > move.
        if self.damage_timer > 0:
            next_anim_state = "hit"
        elif self.weapon.reloading:
            next_anim_state = "reload"
        elif self._shoot_flash > 0:
            next_anim_state = "shoot"
        elif self.crouching:
            next_anim_state = "crouch"
        elif self._move_amt > 0.7:
            next_anim_state = "run"
        elif self._move_amt > 0.15:
            next_anim_state = "walk"
        else:
            next_anim_state = "idle"

        # Preserve the outgoing state/frame and crossfade into the new pose.
        self._set_anim_state(next_anim_state)
        self.anim_blend = min(1.0, self.anim_blend + max(0.0, dt) / 0.16)

        # Body bob driven by the gait cycle (highest mid-stride).
        if self.anim_state in ("walk", "run", "crouch"):
            bob_amount = (0.8 if self.anim_state == "crouch" else
                          (1.8 if self.anim_state == "walk" else 3.4))
            self._bob = abs(math.sin(self._gait * math.pi * 2.0)) * bob_amount
        else:
            self._bob = 0.0

        # Pick the gait frame.  Walk/run use the 4-frame cycle indexed by
        # the gait phase; idle gently breathes through the idle frames.
        if self.anim_state in ("walk", "run", "crouch"):
            self.frame_index = int(self._gait * 8) % 8
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
