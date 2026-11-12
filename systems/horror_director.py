"""Adaptive pacing for ambient horror events and enemy pressure."""
from __future__ import annotations

import random


class HorrorDirector:
    """Adjusts scare pacing from nearby threats, health and elapsed time."""

    def __init__(self, seed=None) -> None:
        self.rng = random.Random(seed)
        self.tension = 0.0
        self.event_timer = self.rng.uniform(18.0, 27.0)
        self.cooldown = 0.0
        self.events_seen = 0

    def update(self, dt: float, player, controller, progression) -> str | None:
        nearby = sum(
            1 for z in controller.zombies
            if z.alive and z.dist(player) < 8.0
        )
        health_pressure = 1.0 - max(0.0, player.hp / max(1.0, player.max_hp))
        threat = min(1.0, nearby / 4.0)
        target = min(1.0, 0.55 * threat + 0.35 * health_pressure
                     + min(0.1, progression.time / 900.0))
        self.tension += (target - self.tension) * min(1.0, dt * 0.35)
        self.cooldown = max(0.0, self.cooldown - dt)
        self.event_timer -= dt
        if self.event_timer > 0 or self.cooldown > 0:
            return None

        # Longer quiet gaps at low tension; shorter gaps when surrounded.
        self.event_timer = self.rng.uniform(24.0, 38.0) * (
            1.0 - 0.45 * self.tension)
        self.cooldown = 9.0
        self.events_seen += 1
        events = (
            "Something moves between the trees...",
            "A distant bell rings once. Then silence.",
            "You hear footsteps that do not match your own.",
            "The forest goes unnaturally quiet.",
        )
        message = self.rng.choice(events)
        progression.notify(message, 3.0)
        return message
