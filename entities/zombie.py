"""Zombie entity: per-type stats, animation and movement state.

The behaviour (detect / pursue / navigate / attack) lives in
:mod:`systems.enemy_ai`; this class owns the data the AI reads and writes.
"""
from __future__ import annotations

import math
import random

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

        self.state = "idle"          # idle | pursue | investigate | attack
        self._attack_timer = 0.0
        self.moving = False
        self.anim_state = "idle"
        self.prev_anim_state = "idle"
        self.prev_frame_index = 0
        self.anim_blend = 1.0
        self.anim_timer = 0.0
        self.frame_index = 0
        self.hit_flash = 0.0
        self._actual_speed = 0.0
        self._action_phase = 0.0

        # AI / navigation
        self.wander_target = None
        self.wander_timer = 0.0
        self.path = None
        self.path_i = 0
        self.repath_timer = 0.0
        self.facing = 1.0
        self.groan_timer = 0.0

        # Cinematic spawn: the zombie is not fully "alive" until it emerges.
        self.spawning = True
        self.emerge_style = "ground"   # ground | fog | forest
        self.emerge_t = 0.0            # 0..1 emergence progress
        self.emerge_total = 1.4        # seconds to fully materialise
        self.spawn_particles = False   # one-shot flag for the FX layer

        # Procedural gait: each zombie has its own phase + asymmetric limb
        # stretch so the shambling never looks mechanical.
        self._gait = random.uniform(0.0, 1.0)
        self._gait_rate = random.uniform(0.85, 1.15)
        self._sway = random.uniform(0.5, 1.0)   # body sway amplitude
        self._sway_ph = random.uniform(0.0, math.pi * 2)
        self._stumble = 0.0                  # seconds until next stumble
        self._stumble_t = 0.0
        self._stumble_dir = 1.0

        # Death + hit reaction
        self.death_fall = random.randint(0, 2)  # 0 fwd, 1 side, 2 back
        self.death_stagger = 0.0
        self._corpse_t = 0.0          # time the corpse stays visible
        self._hit_knock = 0.0         # brief backward recoil
        self._hit_knock_dir = 1.0

        # Per-frame procedural bob for the renderer.
        self._bob = 0.0

        # Zombie-specific gait feel by type.
        self._gait_stretch = {"regular": 0.9, "fast": 1.15,
                              "tank": 0.6, "crawler": 0.55,
                              "exploder": 1.0}.get(ztype, 0.9)
        # Extended AI state support
        self.search_timer = 0.0
        self.stagger_timer = 0.0
        self.suspicion = 0.0
        self.last_known = (x, y)
        self.alerted = False
        self.variation = random.uniform(0.92, 1.08)  # per-zombie variation
        self.speed *= self.variation
        self.detect *= random.uniform(0.95, 1.05)

    # ------------------------------------------------------------------
    @property
    def pos(self):
        return self.x, self.y

    @property
    def depth(self):
        return self.x + self.y

    @property
    def active(self) -> bool:
        """A zombie participates in AI / combat once it has emerged."""
        return self.alive and not self.spawning

    @property
    def bob(self) -> float:
        return getattr(self, "_bob", 0.0)

    # ------------------------------------------------------------------
    def begin_emergence(self, style: str = "ground", duration: float = 1.4):
        """Start a cinematic spawn.  ``style`` picks the visual variant."""
        self.spawning = True
        self.emerge_style = style
        self.emerge_t = 0.0
        self.emerge_total = max(0.6, duration)
        self.spawn_particles = True
        self.state = "idle"
        self.moving = False

    def _step_emergence(self, dt: float) -> bool:
        """Advance the emergence.  Returns True the frame it completes."""
        if not self.spawning:
            return False
        self.emerge_t += dt / self.emerge_total
        if self.emerge_t >= 1.0:
            self.emerge_t = 1.0
            self.spawning = False
            self.state = "pursue"
            self.emerge_style = None
            return True
        return False

    def apply_move(self, vx: float, vy: float, dt: float, grid) -> None:
        """Advance the zombie; gait and facing follow actual displacement."""
        if self.spawning:
            self.moving = False
            return
        dt = max(0.0, min(float(dt), 0.1))
        m = math.hypot(vx, vy)
        # Occasional stumble: brief speed dip + sideways lurch.
        self._stumble -= dt
        if self._stumble <= 0:
            self._stumble = random.uniform(2.0, 5.0)
            self._stumble_t = random.uniform(0.25, 0.5)
            self._stumble_dir = random.choice((-1.0, 1.0))
        speed = self.speed
        if self._stumble_t > 0:
            speed *= 0.35
            self._stumble_t -= dt
        if m > 1e-6:
            dx = vx / m * speed * dt
            dy = vy / m * speed * dt
            # Lateral shuffle during a stumble.
            if self._stumble_t > 0:
                dx += -vy / m * self._stumble_dir * speed * 0.6 * dt
                dy += vx / m * self._stumble_dir * speed * 0.6 * dt
        else:
            dx = dy = 0.0
        # Hit recoil: rear up and back away from the attacker.
        if self._hit_knock > 0:
            k = self._hit_knock * 6.0 * dt
            dx += self._hit_knock_dir * k * 0.4
            dy += self._hit_knock_dir * k * 0.4
            self._hit_knock -= dt

        old_x, old_y = self.x, self.y
        self.x, self.y = grid.move_circle((old_x, old_y), (dx, dy),
                                          self.radius)
        travelled = math.hypot(self.x - old_x, self.y - old_y)
        self._actual_speed = travelled / dt if dt > 0.0 else 0.0
        self.moving = self._actual_speed > 0.05
        if self.moving:
            # Feet cycle in proportion to distance actually walked, so a
            # zombie jammed against geometry never foot-slides.
            self._gait = (self._gait + travelled * 0.8 *
                          self._gait_rate) % 1.0
            # Smoothly turn toward the intended travel direction.
            target = -1.0 if (vx - vy) < 0 else 1.0
            self.facing += (target - self.facing) * min(1.0, dt * 10.0)

    def _set_anim_state(self, state: str) -> None:
        """Blend into a new animation state without a hard frame cut."""
        if state == self.anim_state:
            return
        self.prev_anim_state = self.anim_state
        self.prev_frame_index = self.frame_index
        self.anim_state = state
        self.anim_timer = 0.0
        self.anim_blend = 0.0
        if state == "attack":
            self._action_phase = 0.0

    # ------------------------------------------------------------------
    def on_hit(self, dmg: float, src, knock_dir: float = 1.0) -> None:
        self.hp -= dmg
        self.hit_flash = 0.12
        # Recoil impulse away from the hit source (applied in apply_move).
        self._hit_knock = 0.5
        self._hit_knock_dir = 1.0 if knock_dir >= 0 else -1.0
        # Powerful hits stagger non-tank zombies briefly.
        if dmg >= 20 and self.ztype != "tank":
            self.stagger_timer = max(getattr(self, "stagger_timer", 0.0), 0.18)
        elif dmg >= 35:
            self.stagger_timer = max(getattr(self, "stagger_timer", 0.0), 0.28)
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.spawning = False
            self.state = "dead"
            self.anim_state = "dead"
            self.death_stagger = 0.55   # brief wobble before the fall
            self._corpse_t = 0.9       # corpse lingers, then fades out

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Animation + timers (AI decisions are made by enemy_ai)."""
        dt = max(0.0, min(float(dt), 0.1))
        self._attack_timer = max(0.0, self._attack_timer - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self._hit_knock = max(0.0, self._hit_knock - dt)

        # Cinematic spawn first: the body rises, then control passes to AI.
        if self.spawning:
            done = self._step_emergence(dt)
            self._set_anim_state("emerge")
            self.anim_blend = min(1.0, self.anim_blend + dt * 3.5)
            self.frame_index = int(self.emerge_t * 3) % 3
            if done:
                # First groan now that it's upright.
                self.groan_timer = 0.1
                self.state = "pursue"
                self._attack_timer = 0.6  # brief wind-up before first lunge
            return

        # Death: stagger, then hold the laid-down frame.
        if not self.alive:
            self._set_anim_state("dead")
            self.anim_blend = min(1.0, self.anim_blend + dt * 3.5)
            self.frame_index = self.death_fall % 3
            return

        # Advance the body sway.  The gait itself advances in apply_move,
        # driven by actual displacement, so idle zombies keep their feet
        # planted instead of cycling in place.
        self._sway_ph += dt * (1.6 + self.speed * 0.3)

        # State-based animation selection with a short blend on transition.
        if self.hit_flash > 0 or getattr(self, "stagger_timer", 0.0) > 0:
            state = "hit"
        elif self.state == "attack":
            state = "attack"
            self._action_phase = (self._action_phase + dt * 1.7) % 1.0
        elif self.moving:
            state = "walk"
        else:
            state = "idle"
        self._set_anim_state(state)
        self.anim_blend = min(1.0, self.anim_blend + dt * 3.5)

        if state == "walk":
            self.frame_index = int(self._gait * 4) % 4
        elif state == "attack":
            # Attack wind-up cycles on its own clock so the lunge reads
            # clearly even though the body is stationary.
            self.frame_index = int(self._action_phase * 4) % 4
        elif state == "idle":
            self.anim_timer += dt
            self.frame_index = int(self.anim_timer * 1.2) % 4
        else:
            self.frame_index = 0

        # Body bob + lateral sway for a shambling, off-balance feel.  The
        # walk bob scales with real speed so faster zombies pump more.
        if state == "walk":
            amp = 1.6 + 1.4 * min(1.0, self._actual_speed /
                                  max(0.1, self.speed))
            self._bob = abs(math.sin(self._gait * math.pi)) * amp
        elif state == "attack":
            self._bob = math.sin(self._action_phase * math.pi) * 2.0
        else:
            self._bob = math.sin(self._sway_ph) * 0.8

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "ztype": self.ztype,
                "hp": self.hp}
