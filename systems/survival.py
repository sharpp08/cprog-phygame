"""Lightweight survival resources: stamina and a rechargeable flashlight."""
from __future__ import annotations


class SurvivalSystem:
    def __init__(self) -> None:
        self.stamina = 100.0
        self.max_stamina = 100.0
        self.flashlight_battery = 100.0
        self.flashlight_on = True
        self.low_battery_warned = False

    def toggle_flashlight(self) -> bool:
        if self.flashlight_on:
            self.flashlight_on = False
        elif self.flashlight_battery > 1.0:
            self.flashlight_on = True
        return self.flashlight_on

    def update(self, dt: float, running: bool) -> bool:
        """Update resources; return whether the player may sprint this frame."""
        if self.flashlight_on:
            self.flashlight_battery = max(
                0.0, self.flashlight_battery - 1.15 * dt)
            if self.flashlight_battery <= 0:
                self.flashlight_on = False
        else:
            self.flashlight_battery = min(
                100.0, self.flashlight_battery + 0.32 * dt)

        can_run = self.stamina > 1.0
        if running and can_run:
            self.stamina = max(0.0, self.stamina - 27.0 * dt)
        else:
            self.stamina = min(100.0, self.stamina + 18.0 * dt)
        return can_run

    @property
    def battery_percent(self) -> int:
        return int(round(self.flashlight_battery))

    @property
    def stamina_percent(self) -> int:
        return int(round(self.stamina))
