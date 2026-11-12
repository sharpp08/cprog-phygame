"""Particle system: blood, sparks, smoke, muzzle puffs, fireflies, dust, mist."""
from __future__ import annotations

import math
import random
from typing import List

import pygame


class Particle:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "life", "max_life",
                 "size", "color", "gravity", "fade", "kind")

    def __init__(self, x, y, z, vx, vy, vz, life, size, color,
                 gravity=0.0) -> None:
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.life = life
        self.max_life = life
        self.size = size
        self.color = color
        self.gravity = gravity
        self.fade = 1.0
        self.kind = "generic"

    def update(self, dt: float) -> None:
        self.life -= dt
        self.vz -= self.gravity * dt
        self.z += self.vz * dt
        if self.z < 0:
            self.z = 0.0
            self.vz = 0.0
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.fade = max(0.0, min(1.0, self.life / self.max_life))

    @property
    def alive(self) -> bool:
        return self.life > 0.0


class ParticleSystem:
    MAX_PARTICLES = 600

    def __init__(self) -> None:
        self.particles: List[Particle] = []
        self._ff_timer = 0.0
        self._amb_timer = 0.0
        self._max = self.MAX_PARTICLES
        self._wind = 0.0        # world-space wind drift (from weather)
        self._ambient_world = None

    # ------------------------------------------------------------------
    def set_max(self, n: int) -> None:
        """Quality-driven pool size (recycles the oldest particle)."""
        self._max = max(80, int(n))

    def set_wind(self, wind: float) -> None:
        """Wind strength 0..1 (sign = direction) for drifting particles."""
        self._wind = max(-1.0, min(1.0, float(wind)))


    # ------------------------------------------------------------------
    def _add(self, p: Particle) -> None:
        if len(self.particles) < self._max:
            self.particles.append(p)
        else:
            self.particles[0].life = 0.0
            self.particles[0] = p

    # ------------------------------------------------------------------
    def burst(self, kind: str, x: float, y: float, z: float, count: int,
              color, speed: float = 1.0, life: float = 0.6,
              size: float = 3.0, gravity: float = 0.0,
              upward: bool = False) -> None:
        for _ in range(count):
            ang = random.random() * 3.14159 * 2
            sp = random.uniform(0.3, 1.0) * speed
            vx = math.cos(ang) * sp
            vy = math.sin(ang) * sp
            vz = random.uniform(0.5, 1.5) if upward else \
                random.uniform(-0.2, 0.4)
            c = tuple(int(max(0, min(255, v * random.uniform(0.7, 1.2))))
                      for v in color)
            p = Particle(x, y, z, vx, vy, vz,
                         life * random.uniform(0.6, 1.3),
                         size * random.uniform(0.7, 1.3), c, gravity)
            p.kind = kind
            self._add(p)

    def emit(self, kind: str, x: float, y: float, z: float,
             vx: float, vy: float, vz: float, life: float,
             color, size: float) -> None:
        p = Particle(x, y, z, vx, vy, vz, life, size, color)
        p.kind = kind
        self._add(p)

    # ------------------------------------------------------------------
    def spawn_fireflies(self, world) -> None:
        target = 10
        ff = [p for p in self.particles if p.kind == "firefly"]
        if len(ff) < target:
            for _ in range(target - len(ff)):
                cx, cy = world.shrine
                x = cx + random.uniform(-9, 9)
                y = cy + random.uniform(-9, 9)
                p = Particle(x, y, random.uniform(0.4, 1.4),
                              0.0, 0.0, 0.0,
                              random.uniform(4.0, 8.0), 1.5,
                              (220, 255, 120), 0.0)
                p.kind = "firefly"
                self._add(p)

    # ------------------------------------------------------------------
    def spawn_ambient(self, world, scale: float = 1.0) -> None:
        """Keep a light population of drifting leaves, dust motes and
        shrine embers alive.  Counts scale with the quality preset."""
        if len(self.particles) > self._max * 0.7:
            return                      # protect combat effects
        kinds = {
            "leaf":  int(14 * scale),
            "dust":  int(10 * scale),
            "ember": int(6 * scale),
        }
        for kind, target in kinds.items():
            have = sum(1 for p in self.particles if p.kind == kind)
            for _ in range(max(0, target - have)):
                if kind == "leaf":
                    x = random.uniform(0, world.W)
                    y = random.uniform(0, world.H)
                    p = Particle(x, y, random.uniform(1.0, 2.6),
                                  0.0, 0.0, random.uniform(-0.25, -0.4),
                                  random.uniform(6.0, 12.0),
                                  random.uniform(1.4, 2.6),
                                  random.choice(
                                      [(150, 110, 55), (168, 92, 50),
                                       (120, 130, 70)]))
                elif kind == "dust":
                    x = random.uniform(0, world.W)
                    y = random.uniform(0, world.H)
                    p = Particle(x, y, random.uniform(0.4, 1.6),
                                  0.0, 0.0, 0.0,
                                  random.uniform(4.0, 9.0),
                                  random.uniform(0.8, 1.6),
                                  (190, 185, 170))
                else:  # embers drift up from the shrine fire
                    cx, cy = world.shrine
                    p = Particle(cx + random.uniform(-1.5, 1.5),
                                 cy + random.uniform(-1.5, 1.5),
                                 random.uniform(0.5, 1.0),
                                 random.uniform(-0.2, 0.2),
                                 random.uniform(-0.2, 0.2),
                                 random.uniform(0.5, 1.4),
                                 random.uniform(4.0, 7.0), 1.5,
                                 random.choice(
                                     [(255, 150, 60), (255, 190, 90)]))
                p.kind = kind
                self._add(p)

    # ------------------------------------------------------------------
    def update(self, dt: float, world=None, wind: float = 0.0) -> None:
        w = self._wind if wind == 0.0 else max(-1.0, min(1.0, float(wind)))
        for p in self.particles:
            p.update(dt)
            if p.kind == "firefly":
                p.x += math.sin(p.life * 1.3) * 0.15
                p.y += math.cos(p.life * 1.1) * 0.15
                p.fade = 0.5 + 0.5 * abs(math.sin(p.life * 4.0))
            elif p.kind == "leaf":
                # wind drift + flutter; land and die on the ground
                p.x += (w * 1.6 + math.sin(p.life * 2.1) * 0.35) * dt
                p.y += math.cos(p.life * 1.7) * 0.12 * dt
                p.fade = min(1.0, p.fade * (0.6 + 0.4 * abs(math.sin(p.life * 3))))
            elif p.kind == "dust":
                p.x += (w * 0.5 + math.sin(p.life * 0.9) * 0.15) * dt
                p.fade = 0.35 + 0.3 * abs(math.sin(p.life * 1.3))
        self.particles = [p for p in self.particles if p.alive]
        if world is not None:
            self._ff_timer -= dt
            if self._ff_timer <= 0:
                self._ff_timer = 1.5
                self.spawn_fireflies(world)
            self._amb_timer -= dt
            if self._amb_timer <= 0:
                self._amb_timer = 0.8
                self._ambient_world = world
                self.spawn_ambient(world)


    # ------------------------------------------------------------------
    def draw(self, screen: pygame.Surface, cam, quality: int = 1) -> None:
        for p in self.particles:
            if p.kind == "firefly" and quality < 2:
                continue
            if p.kind in ("leaf", "dust") and quality < 1:
                continue
            if p.kind == "ember" and quality < 1:
                continue
            x, y = cam.iso_to_screen(p.x, p.y, p.z)
            if x < -20 or x > cam.sw + 20 or y < -30 or y > cam.sh + 30:
                continue                # distance culling
            a = int(255 * p.fade)
            scale = max(0.5, float(cam.zoom))
            if p.kind == "firefly":
                pygame.draw.circle(screen, (*p.color, a),
                                   (int(x), int(y)), max(1, int(p.size * scale)))
                pygame.draw.circle(screen, (255, 255, 180, a // 4),
                                   (int(x), int(y)), int(p.size * scale) + 2)
            elif p.kind == "ember":
                pygame.draw.circle(screen, (*p.color, a),
                                   (int(x), int(y)), max(1, int(p.size * scale)))
                pygame.draw.circle(screen, (255, 120, 40, a // 5),
                                   (int(x), int(y)), int(p.size * scale) + 2)
            elif p.kind == "smoke":
                pygame.draw.circle(screen, (*p.color, a // 3),
                                   (int(x), int(y)),
                                   int(p.size * scale * (2 - p.fade)))
            elif p.kind in ("leaf", "dust"):
                r = max(1, int(p.size * scale))
                col = (*p.color, a // (2 if p.kind == "dust" else 1))
                pygame.draw.ellipse(screen, col,
                                    (int(x - r), int(y - r // 2),
                                     r * 2, max(1, r)))
            else:
                pygame.draw.circle(screen, (*p.color, a),
                                   (int(x), int(y)),
                                   max(1, int(p.size * scale * p.fade + 1)))

    def clear(self) -> None:
        self.particles = []
