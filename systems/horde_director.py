"""Performance-bounded, sound-attracted horde pressure director."""
from __future__ import annotations

import math
import random


class HordeDirector:
    """Turns sustained gunfire into a delayed, fair multi-directional threat."""

    def __init__(self, seed=None) -> None:
        self.rng = random.Random(seed)
        self.noise_exposure = 0.0
        self.cooldown = 0.0
        self.hordes_spawned = 0
        self.last_spawn_count = 0

    def update(self, dt, player, controller, survival_time=0.0,
               noise_radius=0.0, noise_timer=0.0):
        dt = max(0.0, min(float(dt), 0.25))
        self.cooldown = max(0.0, self.cooldown - dt)
        loud = noise_radius >= 15.0 and noise_timer > 0.0
        if loud:
            self.noise_exposure = min(8.0, self.noise_exposure + dt)
        else:
            self.noise_exposure = max(0.0, self.noise_exposure - dt * 0.65)

        if self.noise_exposure < 2.2 or self.cooldown > 0:
            return 0
        # A small early response, with a gradual increase over long runs.
        requested = 2 + min(4, int(max(0.0, survival_time) / 180.0))
        active = getattr(controller, "alive_count", len(controller.zombies))
        capacity = max(0, min(requested, 30 - active))
        if capacity <= 0:
            self.noise_exposure = 0.0
            self.cooldown = 24.0
            return 0

        points = list(getattr(controller, "_spawn_points", ()))
        if not points:
            points = [(2, 2), (2, controller.h - 3),
                      (controller.w - 3, 2),
                      (controller.w - 3, controller.h - 3)]
        candidates = []
        for point in points:
            x, y = float(point[0]), float(point[1])
            distance = math.hypot(x - player.x, y - player.y)
            if 8.0 <= distance <= 22.0:
                if not controller.grid.is_blocked(int(x), int(y)):
                    candidates.append((x, y))
        # Fixed map-edge spawn lanes can be too far away or behind the
        # survivor. Add clear radial approach points around the current area.
        for index in range(16):
            angle = (2.0 * math.pi * index) / 16.0
            radius = 11.0 + (index % 3) * 2.0
            x = player.x + math.cos(angle) * radius
            y = player.y + math.sin(angle) * radius
            if not (1.0 <= x < controller.w - 1
                    and 1.0 <= y < controller.h - 1):
                continue
            if controller.grid.is_blocked(int(x), int(y)):
                continue
            candidates.append((x, y))
        # Prefer different approach directions; never spawn beside the player.
        self.rng.shuffle(candidates)
        chosen = []
        for candidate in candidates:
            if all(math.hypot(candidate[0] - other[0],
                              candidate[1] - other[1]) >= 5.0
                   for other in chosen):
                chosen.append(candidate)
            if len(chosen) >= capacity:
                break
        spawned = 0
        for index, (x, y) in enumerate(chosen):
            ztype = "fast" if index == 0 and survival_time > 120 else "regular"
            controller.add_zombie(None, x, y, ztype)
            spawned += 1
        self.noise_exposure = 0.0
        self.cooldown = 48.0
        if spawned:
            self.hordes_spawned += 1
        self.last_spawn_count = spawned
        return spawned
