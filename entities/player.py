"""The player character: movement, aiming and weapon/animation state."""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import config
from engine.movement import (MoveProfile, NEUTRAL, Surface, aim_speed_multiplier,
                             clamp, cycles_per_tile, step_velocity)
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
        # Velocity comes from an acceleration-limited model (engine.movement).
        # Animation is driven by measured post-collision displacement, never
        # requested input, which prevents feet cycling while pressed against
        # geometry.
        self._velocity = (0.0, 0.0)
        self.actual_speed = 0.0
        self._move_amt = 0.0        # 0 (idle)..1 (full run)
        self._cur_speed = 0.0
        self._input_time = 0.0      # seconds of continuous input (jerk limit)
        self._stagger = 0.0         # seconds of reduced control after a hit
        self._fire_slow = 0.0       # seconds of reduced pace after firing
        self.bump_impact = 0.0      # speed into a wall this call (0 if none)
        self.lean = 0.0             # -1..1 screen-x acceleration lean

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
        # Gait phase drives the cached eight-frame walk/run cycle (0..1).
        # ``_gait_total`` is the unwrapped phase: ground contacts (phase 0 and
        # 0.5) are counted from it so footstep sounds land on the planted foot.
        self._gait = 0.0
        self._gait_total = 0.0
        self._last_contact = 0
        self._step_side = 0
        self.footstep_sound = False
        self._last_footstep_state = 0

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

    @property
    def velocity(self) -> Tuple[float, float]:
        return self._velocity

    def sprint_allowed(self, mv: Tuple[float, float]) -> bool:
        """Whether the movement direction may be sprinted (see config)."""
        m = math.hypot(mv[0], mv[1])
        if m < 1e-6 or math.hypot(self.aim[0], self.aim[1]) < 0.04:
            return True
        align = (mv[0] * self.aim[0] + mv[1] * self.aim[1]) / m
        return align >= config.PLAYER_SPRINT_MIN_ALIGN

    def apply_knockback(self, src_x: float, src_y: float, dmg: float) -> None:
        """Shove the player away from ``src`` and briefly reduce control."""
        dx, dy = self.x - src_x, self.y - src_y
        m = math.hypot(dx, dy)
        if m < 1e-6:
            dx, dy, m = 1.0, 0.0, 1.0
        imp = clamp(config.PLAYER_KNOCKBACK_MIN
                    + dmg * config.PLAYER_KNOCKBACK_PER_DMG,
                    config.PLAYER_KNOCKBACK_MIN, config.PLAYER_KNOCKBACK_MAX)
        vx, vy = self._velocity
        self._velocity = (vx + dx / m * imp, vy + dy / m * imp)
        self._stagger = config.PLAYER_STAGGER_TIME

    def _load_factor(self) -> float:
        """Speed factor from the carried weapon and what the hands are doing."""
        f = float(self.weapon.spec.get("handling", 1.0))
        if self.weapon.reloading:
            f *= config.PLAYER_RELOAD_SPEED
        if self._fire_slow > 0.0:
            f *= config.PLAYER_FIRE_SPEED
        return f

    def apply_movement(self, mv: Tuple[float, float], running: bool,
                       dt: float, grid, speed_scale: float = 1.0,
                       surface: Optional[Surface] = None,
                       run_scale: float = 1.0) -> None:
        """Physically simulated movement; gait follows measured displacement.

        Velocity is integrated with finite acceleration, braking, friction and
        sideways grip (:func:`engine.movement.step_velocity`).  The frame is
        split into steps of at most ``PLAYER_PHYSICS_MAX_STEP`` so results do
        not depend on the frame rate.  After collision the blocked part of the
        velocity is removed, so sliding off a wall does not restart from a
        stale vector.  Gait phase and footsteps advance from the actual
        post-collision distance travelled, which prevents foot sliding.
        """
        dt = max(0.0, min(float(dt), 0.1))
        surface = surface or NEUTRAL
        # Edge events for this call.
        self.footstep_sound = False
        self.bump_impact = 0.0

        mag = math.hypot(mv[0], mv[1])
        requested = mag > 1e-6
        wx, wy = (mv[0] / mag, mv[1] / mag) if requested else (0.0, 0.0)
        if running and requested and not self.sprint_allowed(mv):
            running = False

        walk, run = config.PLAYER_WALK_SPEED, config.PLAYER_RUN_SPEED
        scale = max(0.2, min(1.0, speed_scale))
        load = self._load_factor()
        aim_mult = aim_speed_multiplier(wx, wy, self.aim[0], self.aim[1]) \
            if requested else 1.0
        cap_walk = walk * scale * surface.speed * load * aim_mult
        cap = cap_walk
        if running:
            cap = run * scale * surface.speed * load * aim_mult \
                * max(0.5, min(1.0, run_scale))
        accel_mult = math.sqrt(scale * load) * surface.accel

        steps = max(1, int(math.ceil(dt / config.PLAYER_PHYSICS_MAX_STEP)))
        h = dt / steps
        vx0, vy0 = self._velocity
        vx, vy = vx0, vy0
        travelled = 0.0
        sum_dx = sum_dy = 0.0     # collision-resolved displacement
        impact = 0.0
        for _ in range(steps):
            if self._stagger > 0.0:
                self._stagger = max(0.0, self._stagger - h)
            control = 1.0 - (1.0 - config.PLAYER_STAGGER_CONTROL) * min(
                1.0, self._stagger / config.PLAYER_STAGGER_TIME)
            if requested:
                self._input_time += h
            else:
                self._input_time = 0.0
            ramp = config.PLAYER_ACCEL_RAMP_START + (
                1.0 - config.PLAYER_ACCEL_RAMP_START) * min(
                1.0, self._input_time / config.PLAYER_ACCEL_RAMP)
            speed = math.hypot(vx, vy)
            sprintiness = clamp((speed - walk) / (run - walk), 0.0, 1.0)
            profile = MoveProfile(
                max_speed=max(cap, 0.05),
                accel=config.PLAYER_ACCEL_WALK * accel_mult,
                brake=config.PLAYER_BRAKE * surface.grip,
                friction=config.PLAYER_FRICTION * surface.grip
                * (1.0 - config.PLAYER_FRICTION_SPRINT * sprintiness),
                grip=config.PLAYER_GRIP * surface.grip,
                accel_high=config.PLAYER_ACCEL_SPRINT * accel_mult,
                knee=cap_walk if running else 0.0,
                overspeed_decel=config.PLAYER_OVERSPEED_DECEL)
            vx, vy = step_velocity(vx, vy, wx, wy, profile, h,
                                   ramp=ramp, control=control)
            if not requested and math.hypot(vx, vy) < 0.04:
                vx = vy = 0.0

            ox, oy = self.x, self.y
            self.x, self.y = grid.move_circle(
                (ox, oy), (vx * h, vy * h), self.radius)
            ax, ay = self.x - ox, self.y - oy
            travelled += math.hypot(ax, ay)
            sum_dx += ax
            sum_dy += ay

            # Remove the velocity the wall absorbed (slide, don't push).
            bx, by = vx * h - ax, vy * h - ay
            bm = math.hypot(bx, by)
            if bm > 1e-6:
                nx, ny = bx / bm, by / bm
                vn = vx * nx + vy * ny
                if vn > 0.0:
                    vx -= nx * vn
                    vy -= ny * vn
                    impact = max(impact, vn)
        self._velocity = (vx, vy)
        self.bump_impact = impact

        self.actual_speed = travelled / dt if dt > 0.0 else 0.0
        self._cur_speed = self.actual_speed
        self.moving = self.actual_speed > 0.05
        self.running = (running and self.moving and
                        self.actual_speed > config.PLAYER_WALK_SPEED * 1.05)
        blend = 1.0 - math.exp(-16.0 * dt)
        target_amt = min(1.0, self.actual_speed / config.PLAYER_RUN_SPEED)
        self._move_amt += (target_amt - self._move_amt) * blend

        # Lean into acceleration: screen-x component of the velocity change
        # (iso screen_x = x - y).  Braking leans back, a wall hit lurches.
        if dt > 0.0:
            a_sx = ((vx - vx0) - (vy - vy0)) * 0.7071 / dt
            target = clamp(a_sx / config.PLAYER_LEAN_ACCEL_SCALE, -1.0, 1.0)
            k = 1.0 - math.exp(-config.PLAYER_LEAN_RESPONSE * dt)
            self.lean += (target - self.lean) * k

        # Aim has priority for a shooter. If there is no meaningful aim vector,
        # face the collision-resolved travel direction rather than requested
        # input, so wall sliding and diagonal turns cannot flip the sprite wrong.
        if travelled > 1e-6 and math.hypot(*self.aim) < 0.04:
            screen_dx = sum_dx - sum_dy
            if abs(screen_dx) > 1e-5:
                self._facing_target = -1.0 if screen_dx < 0.0 else 1.0

        if travelled > 1e-6:
            # Gait phase follows actual displacement; the stride length blends
            # smoothly with speed.  Footsteps fire on ground contact (phase 0
            # and 0.5) read from the same unwrapped phase, so sound and the
            # visible planted foot cannot drift apart.
            self._gait_total += travelled * cycles_per_tile(self.actual_speed)
            self._gait = self._gait_total % 1.0
            contact = int(self._gait_total * 2.0)
            if contact != self._last_contact:
                self._last_contact = contact
                self._step_side = contact & 1
                self.footstep_sound = True
                self._last_footstep_state = 1
        elif not requested:
            # Settled: keep the gait phase for a seamless next step.
            self._last_footstep_state = 0

    # ------------------------------------------------------------------
    def mark_shoot(self) -> None:
        self._shoot_flash = 0.12
        self._fire_slow = config.PLAYER_FIRE_SLOW_TIME
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
            self._set_anim_state("dead")
            self.anim_blend = min(1.0, self.anim_blend + max(0.0, dt) / 0.20)
            self.frame_index = 0
            return
        self.invuln = max(0.0, self.invuln - dt)
        self.damage_timer = max(0.0, self.damage_timer - dt)
        self.dmg_flash = max(0.0, self.dmg_flash - dt)
        self._shoot_flash = max(0.0, self._shoot_flash - dt)
        self._fire_slow = max(0.0, self._fire_slow - dt)
        self.weapon.update(dt)
        # Smoothly rotate the sprite toward aim; this is frame-rate independent.
        facing_blend = 1.0 - math.exp(-config.PLAYER_TURN_SMOOTH * max(0.0, dt))
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
        elif self.running:
            next_anim_state = "run"
        elif self.moving:
            next_anim_state = "walk"
        else:
            next_anim_state = "idle"

        # Preserve the outgoing state/frame and crossfade into the new pose.
        self._set_anim_state(next_anim_state)
        self.anim_blend = min(1.0, self.anim_blend + max(0.0, dt) / 0.16)

        # Pick the gait frame. Walk/run/crouch share one continuous cycle;
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

    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y, "hp": self.hp,
            "weapons": [w.to_dict() for w in self.weapons],
            "current": self.current,
        }
