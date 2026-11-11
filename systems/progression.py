"""Survival progression: objectives, escalating waves, win and lose states."""
from __future__ import annotations

import math
import random
from typing import List, Tuple

import config


class Progression:
    def __init__(self) -> None:
        self.phase = "explore"
        self.state = "playing"      # playing | won | lost
        self.objective = "Cross the forest and reach the ancient shrine"
        self.score = 0
        self.kills = 0
        self.time = 0.0
        self.shrine_reached = False
        self.wave = 0
        self.wave_total = config.WAVES_AT_SHRINE
        self._wave_alive = 0
        self._spawn_timer = 4.0
        self._shrine_warned = False
        self.message = ""
        self.message_timer = 0.0

    # ------------------------------------------------------------------
    def notify(self, text: str, hold: float = 3.5) -> None:
        self.message = text
        self.message_timer = hold

    def on_kill(self, z) -> None:
        self.score += z.score
        self.kills += 1

    # ------------------------------------------------------------------
    def update(self, dt: float, player, controller, world) -> None:
        self.time += dt
        self.message_timer = max(0.0, self.message_timer - dt)
        if self.state != "playing":
            return
        sx, sy = config.SHRINE_POS

        if self.phase == "explore":
            # continuous spawning, rate grows over time
            self._spawn_timer -= dt
            cap = min(config.ZOMBIE_MAX_ACTIVE,
                      8 + int(self.time / 20))
            if self._spawn_timer <= 0 and controller.alive_count < cap:
                z = controller.spawn_random()
                if z is None:
                    z = controller.spawn_near((random.randint(3, 44),
                                               random.randint(3, 44)))
                self._spawn_timer = random.uniform(
                    3.0, 6.0) - min(3.0, self.time / 40.0)
            d = math.hypot(player.x - sx, player.y - sy)
            if not self._shrine_warned and d < 12:
                self._shrine_warned = True
                self.notify("You can hear the shrine bells in the distance...")
            if d < 3.5:
                self.shrine_reached = True
                self.phase = "shrine"
                self.objective = ("The shrine! Survive the final "
                                  f"{self.wave_total} waves to escape")
                self.notify("The shrine's seal cracks. Waves incoming!", 5.0)
                self.start_wave(world)

        elif self.phase == "shrine":
            if self.wave >= self.wave_total and controller.alive_count == 0:
                self.state = "won"
                self.objective = "You escaped the forest"
                self.notify("You survived! The forest is silent.", 6.0)
                return
            if controller.alive_count == 0 and self.wave < self.wave_total:
                self.start_wave(controller, world)

    def start_wave(self, controller, world) -> None:
        self.wave += 1
        count = int(config.WAVE_BASE_COUNT *
                    (config.WAVE_GROWTH ** (self.wave - 1)))
        spots = world.spawn_wave_around_shrine(count)
        for (x, y, zt) in spots:
            controller.add_zombie(None, x, y, zt)
        self.notify(f"Wave {self.wave} / {self.wave_total}", 3.0)

    # ------------------------------------------------------------------
    def check_lose(self, player) -> bool:
        if player.dead and self.state == "playing":
            self.state = "lost"
            self.objective = "You died in the forest"
            return True
        return False
