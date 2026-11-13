"""Zombie behaviour: detection, pursuit, pathing, attacking and death.

:class:`ZombieController` owns the live zombie list and drives each zombie's
per-frame decision.  Pathfinding is delegated to :class:`systems.navigation.
Navigation`, audio and particles are injected so this module stays testable.
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, List, Optional, Tuple

import config

if TYPE_CHECKING:
    from entities.zombie import Zombie


class ZombieController:
    # Seconds each emergence style takes to fully materialise.
    _EMERGE_TIME = {"ground": 1.5, "fog": 2.1, "forest": 1.7}

    def __init__(self, grid, nav, w: int, h: int) -> None:
        self.grid = grid
        self.nav = nav
        self.w = w
        self.h = h
        self.zombies: List = []
        self._spawn_points: List[Tuple[int, int]] = []
        self._groan_timer = 0.0
        self._audio = None
        self._particles = None
        self._player = None
        self._world = None
        self.noise_pos = None
        self.noise_radius = 0.0
        self.noise_timer = 0.0
        self.safe_zones = []
        self.rain_amount = 0.0

    # ------------------------------------------------------------------
    def set_context(self, player, audio, particles,
                    spawn_points: List[Tuple[int, int]],
                    world=None) -> None:
        self._player = player
        self._audio = audio
        self._particles = particles
        self._world = world
        self._spawn_points = spawn_points

    def emit_noise(self, x: float, y: float, radius: float,
                   duration: float = 1.0) -> None:
        """Let nearby zombies investigate a loud player action."""
        self.noise_pos = (float(x), float(y))
        self.noise_radius = max(self.noise_radius, float(radius))
        self.noise_timer = max(self.noise_timer, float(duration))

    def add_zombie(self, z, x: float, y: float, ztype: str = "regular",
                   emerge: bool = True, style: str = None,
                   duration: float = None) -> "Zombie":
        from entities.zombie import Zombie
        z = Zombie(x, y, ztype)
        z._repath_cd = random.uniform(0.4, 0.8)
        z._tx = self._player.x if self._player else x
        z._ty = self._player.y if self._player else y
        if style is None:
            style = self._pick_emerge_style(x, y)
        if emerge:
            z.begin_emergence(style,
                              duration if duration else self._EMERGE_TIME[style])
        else:
            z.spawning = False
            z.state = "pursue"
        self.zombies.append(z)
        if self._audio:
            self._audio.play("zombie_emerge" if style in ("fog", "forest")
                             else "zombie_groan")
        return z

    def _pick_emerge_style(self, x: float, y: float) -> str:
        """Choose a cinematic spawn variant from the local environment.

        Fog over water, forest ambush next to dense cover, otherwise the
        classic ground emergence.
        """
        w = self._world
        if w is not None:
            tile = w.tiles[int(y)][int(x)]
            if tile in (config.T_WATER, config.T_LILY, config.T_BRIDGE):
                return "fog"
            near_cover = any(
                o.in_rect(int(x) - 1, int(y) - 1,
                          int(x) + 1, int(y) + 1, 0.0)
                for o in getattr(w, "obstacles", ())
                if getattr(o, "kind", None) in ("tree", "bush"))
            if near_cover:
                return "forest"
        return "ground"

    def spawn_random(self) -> Optional["Zombie"]:
        return self.spawn_near(random.choice(self._spawn_points)
                               if self._spawn_points else (2, 2))

    def spawn_near(self, pos: Tuple[int, int]) -> Optional["Zombie"]:
        """Spawn a zombie at the best spawn point closest to ``pos``."""
        if not self._spawn_points:
            self._spawn_points = [(2, 2), (2, self.h - 3),
                                  (self.w - 3, 2), (self.w - 3, self.h - 3)]
        best = min(self._spawn_points,
                   key=lambda s: (s[0] - pos[0]) ** 2 + (s[1] - pos[1]) ** 2)
        x, y = best[0] + random.uniform(-0.5, 0.5), \
            best[1] + random.uniform(-0.5, 0.5)
        weights = [("regular", 0.40), ("fast", 0.19), ("tank", 0.08),
                   ("crawler", 0.08), ("exploder", 0.06),
                   ("screamer", 0.05), ("armored", 0.06), ("stalker", 0.08)]
        r = random.random()
        acc = 0.0
        ztype = "regular"
        for name, w in weights:
            acc += w
            if r <= acc:
                ztype = name
                break
        z = self.add_zombie(None, x, y, ztype)
        if self._audio:
            self._audio.play("zombie_groan")
        return z

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        p = self._player
        if p is None:
            return
        self.noise_timer = max(0.0, self.noise_timer - dt)
        if self.noise_timer <= 0:
            self.noise_radius = 0.0
            self.noise_pos = None
        # ambient groans
        self._groan_timer -= dt
        if self._groan_timer <= 0 and self.zombies:
            self._groan_timer = random.uniform(2.0, 4.0)
            if self._audio:
                audible = min(
                    (z for z in self.zombies if z.alive and not z.spawning),
                    key=lambda z: z.dist(p), default=None)
                if audible is not None and hasattr(self._audio, "play_spatial"):
                    relative_x = (audible.x - p.x) - (audible.y - p.y)
                    self._audio.play_spatial(
                        "zombie_groan", relative_x, audible.dist(p), 24.0)
                else:
                    self._audio.play("zombie_groan")
        for z in self.zombies:
            # Still emerging: let the spawn cinematics run, no AI yet.
            if z.spawning:
                z.update(dt)
                self._emit_spawn_fx(z)
                continue
            z._tx, z._ty = p.x, p.y
            z.update(dt)
            self._behaviour(z, dt, p)
        self.zombies = [z for z in self.zombies if z.alive]

    # ------------------------------------------------------------------
    def _emit_spawn_fx(self, z) -> None:
        """Cinematic particle cues while a zombie materialises."""
        if not z.spawn_particles:
            return
        if self._particles is None:
            return
        prog = z.emerge_t
        style = z.emerge_style
        if style == "ground" and prog < 0.6:
            # Dirt churns as the body breaks the surface.
            self._particles.burst(
                "smoke", z.x, z.y, 0.1, 2, (90, 70, 50),
                speed=0.5, life=0.7, size=4.0, upward=True)
            z.spawn_particles = False
        elif style == "fog" and prog > 0.15 and prog < 0.85:
            # Thick fog gathers around the silhouette.
            self._particles.burst(
                "smoke", z.x, z.y, 0.3, 1, (150, 165, 175),
                speed=0.3, life=1.2, size=6.0)
        elif style == "forest" and prog > 0.4 and prog < 0.9:
            # Leaves scatter as it breaks the cover.
            self._particles.burst(
                "leaf", z.x, z.y, 0.4, 2, (150, 110, 55),
                speed=0.6, life=0.8, size=2.0)

    def _separation(self, z, dt: float):
        """Steer away from nearby zombies to avoid stacking/clumping."""
        sx = sy = 0.0
        count = 0
        for other in self.zombies:
            if other is z or not other.alive or getattr(other, "spawning", False):
                continue
            dx = z.x - other.x
            dy = z.y - other.y
            d2 = dx * dx + dy * dy
            min_d = z.radius + other.radius + 0.15
            if d2 < min_d * min_d and d2 > 1e-6:
                d = d2 ** 0.5
                push = (min_d - d) / min_d
                sx += (dx / d) * push
                sy += (dy / d) * push
                count += 1
        if count:
            return sx, sy
        return 0.0, 0.0

    # ------------------------------------------------------------------
    def _behaviour(self, z, dt: float, p) -> None:
        if not z.alive:
            return
        d = z.dist(p)
        # temporary safe zone: lose trail while survivor hides in start camp
        if any(((p.x - sx) ** 2 + (p.y - sy) ** 2) <= radius ** 2
               for sx, sy, radius in self.safe_zones):
            z.state = "wandering"
            z.search_timer = 0.0
            z.apply_move(0.0, 0.0, dt, self.grid)
            return
        # stagger interrupts actions briefly
        z.stagger_timer = max(0.0, getattr(z, "stagger_timer", 0.0) - dt)
        if z.stagger_timer > 0:
            z.state = "staggering"
            z.apply_move(0.0, 0.0, dt, self.grid)
            return

        # noise investigation
        noise_target = None
        if self.noise_pos is not None and self.noise_timer > 0:
            nd = ((z.x - self.noise_pos[0]) ** 2 +
                  (z.y - self.noise_pos[1]) ** 2) ** 0.5
            masked_radius = self.noise_radius * (1.0 - 0.28 * self.rain_amount)
            if nd <= masked_radius:
                noise_target = self.noise_pos

        # detection + memory
        can_see = self._can_see_player(z, p, d)
        z._scream_timer = max(0.0, getattr(z, "_scream_timer", 0.0) - dt)
        if can_see:
            z.last_known = (p.x, p.y)
            z.search_timer = 3.5
            z.suspicion = min(1.0, getattr(z, "suspicion", 0.0) + dt * 1.5)
            z.alerted = True
            # group alert: nearby zombies react
            self._alert_nearby(z, 6.0)
            if z.ztype == "screamer" and z._scream_timer <= 0.0:
                z._scream_timer = 18.0
                self._alert_nearby(z, 14.0)
                if self._audio:
                    self._audio.play("zombie_scream")
        else:
            z.suspicion = max(0.0, getattr(z, "suspicion", 0.0) - dt * 0.4)
            z.search_timer = max(0.0, getattr(z, "search_timer", 0.0) - dt)

        # state selection
        if d <= z.attack_range and can_see:
            z.state = "attack"
        elif can_see:
            z.state = "pursue"
        elif noise_target is not None:
            z.state = "investigating"
        elif z.ztype == "stalker" and z.search_timer > 0:
            z.state = "stalking"
        elif z.suspicion > 0.35:
            z.state = "investigating"
        elif z.search_timer > 0 and getattr(z, "last_known", None):
            z.state = "searching"
        elif z.wander_target is not None or z.repath_timer > 0:
            z.state = "wandering"
        else:
            z.state = "idle"

        if z.state in ("pursue", "investigating", "searching", "stalking"):
            z.repath_timer -= dt
            if z.state == "pursue":
                # Different approach lanes reduce enemy stacking.
                angle = math.atan2(z.y - p.y, z.x - p.x)
                target = (p.x + math.cos(angle) * 0.75,
                          p.y + math.sin(angle) * 0.75)
            elif z.state == "investigating" and noise_target is not None:
                target = noise_target
            else:
                target = getattr(z, "last_known", (p.x, p.y))
            if ((target[0] - z.x) ** 2 + (target[1] - z.y) ** 2) < 0.20:
                z.apply_move(0.0, 0.0, dt, self.grid)
                if z.state == "searching":
                    z.search_timer = max(0.0, z.search_timer - dt * 2.0)
                return
            if z.repath_timer <= 0 or z.path is None:
                z._tx, z._ty = target[0], target[1]
                self.nav.plan(z)
                z.repath_timer = z._repath_cd
            vx, vy = self.nav.velocity(z, target[0], target[1])
            if abs(vx) + abs(vy) < 1e-8:
                # stuck: force a short wander repath
                z.path = None
                z.repath_timer = 0.0
                return
            sx, sy = self._separation(z, dt)
            vx += sx * 0.9
            vy += sy * 0.9
            spd_mult = 1.0
            if z.ztype == "crawler":
                spd_mult = 0.85
            elif z.state == "stalking":
                spd_mult = 0.72
            z.apply_move(vx * spd_mult, vy * spd_mult, dt, self.grid)
        elif z.state == "attack":
            z.apply_move(0.0, 0.0, dt, self.grid)
            if z._attack_timer <= 0 and d <= z.attack_range * 1.2:
                z._attack_timer = z.attack_cd
                dmg = z.damage
                # exploder deals extra damage up close and hurts itself
                if z.ztype == "exploder" and d < 1.4:
                    dmg *= 1.6
                    z.hp -= 8
                    if self._particles:
                        self._particles.burst("smoke", z.x, z.y, 0.3, 10,
                                              (160, 120, 60), speed=1.8,
                                              life=0.5, upward=True)
                    if z.hp <= 0:
                        self.kill(z)
                        return
                p.take_damage(dmg)
                if self._audio:
                    self._audio.play("zombie_hit")
                if self._particles:
                    self._particles.burst(
                        "blood", p.x, p.y, 0.4, 6, (150, 30, 30),
                        speed=1.2, life=0.5, upward=True)
            if d > z.attack_range * 1.5:
                z.state = "pursue"
        else:  # idle / wandering
            z.repath_timer -= dt
            if z.wander_target is None or z.repath_timer <= 0:
                z.wander_target = self._rand_walk_target(z)
                z.path = self.nav.a_star((int(z.x), int(z.y)),
                                          z.wander_target)
                z.path_i = 0
                z.repath_timer = random.uniform(1.5, 3.5)
            if z.path:
                vx, vy = self.nav.velocity(z, z.wander_target[0],
                                            z.wander_target[1])
                z.apply_move(vx * 0.45, vy * 0.45, dt, self.grid)


    def _can_see_player(self, z, player, distance=None) -> bool:
        """Check range, stealth, weather and solid geometry before detection."""
        distance = z.dist(player) if distance is None else distance
        flashlight = bool(getattr(player, "flashlight_on", True))
        crouching = bool(getattr(player, "crouching", False))
        range_scale = 1.12 if flashlight else 0.68
        if crouching:
            range_scale *= 0.58
        range_scale *= 1.0 - 0.18 * max(0.0, min(1.0, self.rain_amount))
        if distance >= z.detect * range_scale:
            return False
        steps = max(1, int(distance / 0.45))
        for index in range(1, steps):
            t = index / steps
            x = z.x + (player.x - z.x) * t
            y = z.y + (player.y - z.y) * t
            if self.grid.is_blocked(int(x), int(y)):
                return False
        return True

    def _alert_nearby(self, source, radius: float) -> None:
        """Share last known player position with nearby zombies."""
        lk = getattr(source, "last_known", None)
        if lk is None:
            return
        r2 = radius * radius
        for z in self.zombies:
            if z is source or not z.alive or getattr(z, "spawning", False):
                continue
            dx = z.x - source.x
            dy = z.y - source.y
            if dx * dx + dy * dy <= r2:
                z.last_known = lk
                z.search_timer = max(getattr(z, "search_timer", 0.0), 2.0)
                z.suspicion = max(getattr(z, "suspicion", 0.0), 0.5)
                z.alerted = True
                if z.state in ("idle", "wandering"):
                    z.state = "investigating"

    def _rand_walk_target(self, z):
        for _ in range(6):
            tx = int(random.randint(2, self.w - 3))
            ty = int(random.randint(2, self.h - 3))
            if not self.grid.is_blocked(tx, ty):
                return tx, ty
        return int(z.x), int(z.y)

    # ------------------------------------------------------------------
    def kill(self, z) -> int:
        """Remove a zombie; returns its score."""
        z.alive = False
        if self._particles:
            self._particles.burst(
                "blood", z.x, z.y, 0.3, 14, (120, 40, 30),
                speed=1.6, life=0.7, size=3.0, upward=True)
            self._particles.burst(
                "smoke", z.x, z.y, 0.2, 6, (80, 80, 80),
                speed=0.4, life=1.2, size=5.0)
        if self._audio:
            self._audio.play("zombie_die")
        return z.score

    @property
    def alive_count(self) -> int:
        return len([z for z in self.zombies if z.alive and not z.spawning])
