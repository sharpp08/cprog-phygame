"""Zombie behaviour: detection, pursuit, pathing, attacking and death.

:class:`ZombieController` owns the live zombie list and drives each zombie's
per-frame decision.  Pathfinding is delegated to :class:`systems.navigation.
Navigation`, audio and particles are injected so this module stays testable.
"""
from __future__ import annotations

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
        weights = [0.6, 0.3, 0.1]
        r = random.random()
        ztype = "regular" if r < weights[0] else (
            "fast" if r < weights[0] + weights[1] else "tank")
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

    # ------------------------------------------------------------------
    def _behaviour(self, z, dt: float, p) -> None:
        if not z.alive:
            return
        d = z.dist(p)
        # The abandoned starting camp is a temporary safe zone. Enemies
        # lose the trail while the survivor is inside its boundary.
        if any(((p.x - sx) ** 2 + (p.y - sy) ** 2) <= radius ** 2
               for sx, sy, radius in self.safe_zones):
            z.state = "idle"
            z.apply_move(0.0, 0.0, dt, self.grid)
            return
        # Running and gunfire carry farther than cautious walking.
        noise_target = None
        if self.noise_pos is not None and self.noise_timer > 0:
            nd = ((z.x - self.noise_pos[0]) ** 2 +
                  (z.y - self.noise_pos[1]) ** 2) ** 0.5
            if nd <= self.noise_radius:
                noise_target = self.noise_pos
        # State machine: attack visible targets, investigate sounds, then
        # resume normal detection and patrol behaviour.
        if d <= z.attack_range:
            z.state = "attack"
        elif d < z.detect or noise_target is not None:
            z.state = "investigate" if noise_target is not None and d >= z.detect else "pursue"
        else:
            z.state = "idle"

        if z.state in ("pursue", "investigate"):
            z.repath_timer -= dt
            target = noise_target if z.state == "investigate" else (p.x, p.y)
            if ((target[0] - z.x) ** 2 + (target[1] - z.y) ** 2) < 0.16:
                z.apply_move(0.0, 0.0, dt, self.grid)
                return
            if z.repath_timer <= 0 or z.path is None:
                z._tx, z._ty = target[0], target[1]
                self.nav.plan(z)
                z.repath_timer = z._repath_cd
            vx, vy = self.nav.velocity(z, target[0], target[1])
            if abs(vx) + abs(vy) < 1e-8:
                return
            z.apply_move(vx, vy, dt, self.grid)
        elif z.state == "attack":
            z.apply_move(0.0, 0.0, dt, self.grid)
            if z._attack_timer <= 0 and d <= z.attack_range * 1.2:
                z._attack_timer = z.attack_cd
                p.take_damage(z.damage)
                if self._audio:
                    self._audio.play("zombie_hit")
                if self._particles:
                    self._particles.burst(
                        "blood", p.x, p.y, 0.4, 6, (150, 30, 30),
                        speed=1.2, life=0.5, upward=True)
            # back to chasing once the player steps away
            if d > z.attack_range * 1.5:
                z.state = "pursue"
        else:  # idle wander
            z.repath_timer -= dt
            if z.wander_target is None or z.repath_timer <= 0:
                z.wander_target = self._rand_walk_target(z)
                z.path = self.nav.a_star((int(z.x), int(z.y)),
                                          z.wander_target)
                z.path_i = 0
                z.repath_timer = random.uniform(2.0, 4.0)
            if z.path:
                vx, vy = self.nav.velocity(z, z.wander_target[0],
                                            z.wander_target[1])
                # walk slowly when idle
                z.apply_move(vx * 0.5, vy * 0.5, dt, self.grid)

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
