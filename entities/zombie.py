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
    RUN_THRESHOLDS = {
        "regular": 0.66, "fast": 0.42, "tank": 0.78,
        "crawler": 0.55, "exploder": 0.62, "screamer": 0.62,
        "armored": 0.80, "stalker": 0.88,
    }
    CHASE_STATES = ("pursue", "investigating", "searching")

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
        # Cycles per world tile: short-stride runners cycle faster while
        # heavy infected cover more ground per step. Small variation keeps
        # individual zombies from moving in synchronized lockstep.
        # Gait rates are calibrated so speed/gait_rate gives 1.2-2.6 tiles
        # per full cycle (0.6-1.3 per footfall), matching natural strides.
        gait_rates = {
            "regular": 0.57, "fast": 0.82, "tank": 0.595,
            "crawler": 0.923, "exploder": 0.95, "screamer": 0.607,
            "armored": 0.634, "stalker": 0.90,
        }
        self._gait_rate = gait_rates.get(ztype, 0.68) * random.uniform(0.95, 1.05)
        self._sway = random.uniform(0.5, 1.0)   # body sway amplitude
        self._sway_ph = random.uniform(0.0, math.pi * 2)
        self._stumble = random.uniform(2.0, 5.0)  # seconds until next stumble
        self._stumble_t = 0.0
        self._stumble_dir = 1.0

        # Death + hit reaction
        self.death_fall = random.randint(0, 2)  # 0 fwd, 1 side, 2 back
        self.death_stagger = 0.0
        self._corpse_t = 0.0          # time the corpse stays visible
        self._hit_knock = 0.0         # brief backward recoil
        self._hit_knock_dir = (0.0, 0.0)

        # Zombie-specific gait feel by type.
        self._gait_stretch = {"regular": 0.9, "fast": 1.15,
                              "tank": 0.6, "crawler": 0.55,
                              "exploder": 1.0, "screamer": 0.95,
                              "armored": 0.62, "stalker": 1.05}.get(ztype, 0.9)
        # Extended AI state support
        self.search_timer = 0.0
        self.stagger_timer = 0.0
        self.suspicion = 0.0
        self.last_known = (x, y)
        self.alerted = False
        self.variation = random.uniform(0.92, 1.08)  # per-zombie variation
        self.speed *= self.variation
        self._speed_current = 0.0
        self._velocity = (0.0, 0.0)  # collision-resolved world-space velocity
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
        """Move with archetype-specific inertia; gait follows resolved travel.

        AI supplies a desired direction, not a teleport velocity.  This method
        integrates acceleration, braking, stumble impulses and hit recoil,
        then feeds collision-resolved displacement back into velocity.
        """
        if self.spawning:
            self.moving = False
            return
        dt = max(0.0, min(float(dt), 0.1))
        requested_mag = math.hypot(vx, vy)
        has_target = requested_mag > 1e-6

        # A stumble is a timed gait interruption, not a permanent random
        # multiplier. It only starts while the zombie is actually moving.
        if has_target:
            self._stumble -= dt
            if self._stumble <= 0.0 and self._stumble_t <= 0.0:
                self._stumble = random.uniform(2.0, 5.0)
                self._stumble_t = random.uniform(0.25, 0.5)
                self._stumble_dir = random.choice((-1.0, 1.0))

        target_factor = (0.68 if self.state in ("idle", "wandering", "stalking")
                         else 1.0)
        # AI uses the magnitude of its steering vector for intentional speed
        # modifiers (crawler pace, stalking and wandering). Clamp repulsion
        # blends so separation cannot accidentally accelerate an infected.
        input_scale = min(1.0, requested_mag)
        target_speed = (self.speed * target_factor * input_scale
                        if has_target else 0.0)
        direction_x = vx / requested_mag if has_target else 0.0
        direction_y = vy / requested_mag if has_target else 0.0

        if self._stumble_t > 0.0:
            if has_target:
                target_speed *= 0.42
                # A short lateral catch-step interrupts the straight pursuit line.
                lateral = self._stumble_dir * 0.22
                direction_x, direction_y = (
                    direction_x - direction_y * lateral,
                    direction_y + direction_x * lateral)
                direction_mag = math.hypot(direction_x, direction_y) or 1.0
                direction_x /= direction_mag
                direction_y /= direction_mag
            self._stumble_t = max(0.0, self._stumble_t - dt)

        speed_blend = 1.0 - math.exp(-1.8 * dt)
        self._speed_current += (target_speed - self._speed_current) * speed_blend
        desired_vx = direction_x * self._speed_current
        desired_vy = direction_y * self._speed_current

        # Fast infected react quickly; heavy bodies need more time to redirect.
        accel_rates = {
            "regular": 6.5, "fast": 10.0, "tank": 2.8,
            "crawler": 5.5, "exploder": 5.8, "screamer": 5.0,
            "armored": 3.2, "stalker": 8.0,
        }
        brake_rates = {
            "regular": 7.5, "fast": 9.0, "tank": 2.4,
            "crawler": 5.0, "exploder": 5.5, "screamer": 5.0,
            "armored": 2.8, "stalker": 8.0,
        }
        response = accel_rates.get(self.ztype, 6.0) if has_target else \
                   brake_rates.get(self.ztype, 6.0)
        blend = 1.0 - math.exp(-response * dt)
        current_vx, current_vy = self._velocity
        current_vx += (desired_vx - current_vx) * blend
        current_vy += (desired_vy - current_vy) * blend
        dx, dy = current_vx * dt, current_vy * dt

        # Recoil is a decaying impulse along the vector from the hit source
        # through the zombie, rather than an arbitrary diagonal displacement.
        if self._hit_knock > 0.0:
            impulse = self._hit_knock * 5.0 * dt
            dx += self._hit_knock_dir[0] * impulse
            dy += self._hit_knock_dir[1] * impulse
            self._hit_knock = max(0.0, self._hit_knock - dt)

        old_x, old_y = self.x, self.y
        self.x, self.y = grid.move_circle((old_x, old_y), (dx, dy),
                                          self.radius)
        actual_dx = self.x - old_x
        actual_dy = self.y - old_y
        travelled = math.hypot(actual_dx, actual_dy)
        self._actual_speed = travelled / dt if dt > 0.0 else 0.0
        self._velocity = ((actual_dx / dt, actual_dy / dt)
                          if dt > 0.0 else (0.0, 0.0))
        self.moving = self._actual_speed > 0.05
        if self.moving:
            # Foot phase is distance-driven: blocked enemies cannot foot-slide.
            cycle_rate = (self._gait_rate if self._uses_run_cycle()
                          else self._gait_rate / 0.70)
            self._gait = (self._gait + travelled * cycle_rate) % 1.0
            screen_dx = actual_dx - actual_dy
            if abs(screen_dx) > 1e-5:
                target = -1.0 if screen_dx < 0.0 else 1.0
                turn_blend = 1.0 - math.exp(-10.0 * dt)
                self.facing += (target - self.facing) * turn_blend

    def _uses_run_cycle(self) -> bool:
        speed_ratio = self._actual_speed / max(0.1, self.speed)
        return (self.state in self.CHASE_STATES and
                speed_ratio >= self.RUN_THRESHOLDS.get(self.ztype, 0.66))

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
    def on_hit(self, dmg: float, src, knock_dir: float | tuple[float, float] = 1.0) -> None:
        if self.ztype == "armored":
            dmg *= 0.58
        self.hp -= dmg
        self.hit_flash = 0.12
        # Recoil impulse away from the hit source (applied in apply_move).
        self._hit_knock = 0.5
        if isinstance(knock_dir, (tuple, list)) and len(knock_dir) >= 2:
            kx, ky = float(knock_dir[0]), float(knock_dir[1])
            km = math.hypot(kx, ky) or 1.0
            self._hit_knock_dir = (kx / km, ky / km)
        else:
            # Backwards-compatible scalar input: horizontal recoil only.
            self._hit_knock_dir = (1.0 if float(knock_dir) >= 0 else -1.0, 0.0)
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
            # update() performs the state change so the last live pose can
            # crossfade into the authored death frame instead of hard-cutting.
            self.death_stagger = 0.55   # brief wobble before the fall
            self._corpse_t = 0.9       # corpse lingers, then fades out

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Animation + timers (AI decisions are made by enemy_ai)."""
        dt = max(0.0, min(float(dt), 0.1))
        self._attack_timer = max(0.0, self._attack_timer - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)

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
            # Every infected archetype has a distinct run cycle. Heavy types
            # need a higher speed ratio before their lumbering sprint engages;
            # the crawler uses its low, fast crawl cycle instead.
            state = "run" if self._uses_run_cycle() else "walk"
        else:
            state = "idle"
        self._set_anim_state(state)
        self.anim_blend = min(1.0, self.anim_blend + dt * 3.5)

        if state in ("walk", "run"):
            self.frame_index = int(self._gait * 8) % 8
        elif state == "attack":
            # Attack wind-up cycles on its own clock so the lunge reads
            # clearly even though the body is stationary.
            self.frame_index = int(self._action_phase * 4) % 4
        elif state == "idle":
            self.anim_timer += dt
            self.frame_index = int(self.anim_timer * 1.2) % 4
        else:
            self.frame_index = 0

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "ztype": self.ztype,
                "hp": self.hp}
