"""Adaptive horror pacing with tension tiers and deliberate recovery windows."""
from __future__ import annotations

import random


class HorrorDirector:
    """Paces suspense from threat, health, noise, ammunition and survival time."""

    LEVELS = ("quiet", "uneasy", "danger", "critical")

    def __init__(self, seed=None) -> None:
        self.rng = random.Random(seed)
        self.tension = 0.0
        self.level = "quiet"
        self.event_timer = self.rng.uniform(18.0, 27.0)
        self.cooldown = 0.0
        self.events_seen = 0
        self.recovery = 0.0

    def update(self, dt: float, player, controller, progression,
               survival=None, player_noise: float = 0.0,
               rain: float = 0.0) -> str | None:
        dt = max(0.0, min(float(dt), 0.25))
        nearby = sum(1 for z in controller.zombies
                     if z.alive and not getattr(z, "spawning", False)
                     and z.dist((player.x, player.y)) < 9.0)
        health_pressure = 1.0 - max(
            0.0, min(1.0, player.hp / max(1.0, player.max_hp)))
        threat = min(1.0, nearby / 5.0)
        ammo_pressure = 0.0
        if player is not None and getattr(player, "weapons", None):
            weapon = player.weapon
            reserve = getattr(weapon, "reserve", 0)
            mag = getattr(weapon, "mag", 0)
            capacity = max(1, getattr(weapon, "mag_size", 12))
            ammo_pressure = 1.0 - min(1.0, (mag + reserve) / (capacity * 2.0))
        noise_pressure = min(1.0, max(0.0, player_noise) / 20.0)
        elapsed_pressure = min(0.1, max(0.0, progression.time) / 900.0)
        target = min(1.0, 0.48 * threat + 0.27 * health_pressure
                     + 0.12 * ammo_pressure + 0.08 * noise_pressure
                     + elapsed_pressure)
        if self.recovery > 0:
            self.recovery = max(0.0, self.recovery - dt)
            target = min(target, 0.28)
        # Smooth both escalation and release; release is intentionally faster
        # so a successful escape creates a genuine breathing space.
        rate = 0.55 if target > self.tension else 0.24
        self.tension += (target - self.tension) * min(1.0, dt * rate)
        previous = self.level
        if self.tension < 0.22:
            self.level = "quiet"
        elif self.tension < 0.48:
            self.level = "uneasy"
        elif self.tension < 0.76:
            self.level = "danger"
        else:
            self.level = "critical"

        self.cooldown = max(0.0, self.cooldown - dt)
        self.event_timer -= dt
        if self.event_timer > 0 or self.cooldown > 0:
            return None

        # Never stack a scripted scare on top of an active close attack.
        if nearby >= 3:
            self.event_timer = 8.0
            return None
        low = 26.0 if self.level == "quiet" else 17.0
        high = 42.0 if self.level in ("quiet", "uneasy") else 29.0
        self.event_timer = self.rng.uniform(low, high)
        self.cooldown = 12.0
        self.events_seen += 1
        events = [
            "A branch snaps somewhere beyond the trees.",
            "A distant bell rings once. Then silence.",
            "Footsteps answer yours from the dark.",
            "The forest goes unnaturally quiet.",
        ]
        if rain > 0.45:
            events.append("Something heavy moves through the rain nearby.")
        if self.level in ("danger", "critical"):
            events.extend([
                "A shape slips behind the tree line.",
                "A low growl rises from somewhere behind you.",
            ])
        message = self.rng.choice(events)
        progression.notify(message, 3.0)
        return message

    def begin_recovery(self, seconds: float = 16.0) -> None:
        """Give players a short, earned lull after escaping nearby threats."""
        self.recovery = max(self.recovery, max(0.0, float(seconds)))
