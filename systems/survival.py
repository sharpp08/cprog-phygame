"""Survival resources: stamina, finite flashlight cells and scavenging."""
from __future__ import annotations


class SurvivalSystem:
    def __init__(self) -> None:
        self.stamina = 100.0
        self.max_stamina = 100.0
        self.flashlight_battery = 100.0
        self.flashlight_on = True
        self.low_battery_warned = False
        self.battery_cells = 2
        self.scrap = 0

    def toggle_flashlight(self) -> bool:
        if self.flashlight_on:
            self.flashlight_on = False
        elif self.flashlight_battery > 1.0:
            self.flashlight_on = True
        return self.flashlight_on

    def replace_battery(self) -> bool:
        """Install one spare cell; returns False when none are available."""
        if self.battery_cells <= 0 or self.flashlight_battery >= 98.0:
            return False
        self.battery_cells -= 1
        self.flashlight_battery = 100.0
        self.flashlight_on = True
        self.low_battery_warned = False
        return True

    def add_battery_cells(self, amount: int = 1) -> None:
        self.battery_cells = max(0, min(9, self.battery_cells + int(amount)))

    def update(self, dt: float, running: bool) -> bool:
        """Update resources; return whether the player may sprint this frame."""
        dt = max(0.0, min(float(dt), 0.25))
        if self.flashlight_on:
            self.flashlight_battery = max(
                0.0, self.flashlight_battery - 1.15 * dt)
            if self.flashlight_battery <= 0:
                self.flashlight_on = False
        # A switched-off cell does not recharge: replacement cells are loot.

        can_run = self.stamina > 1.0
        if running and can_run:
            self.stamina = max(0.0, self.stamina - 27.0 * dt)
        else:
            self.stamina = min(100.0, self.stamina + 18.0 * dt)
        return can_run

    def add_scrap(self, amount: int = 1) -> None:
        self.scrap = max(0, self.scrap + int(amount))

    def craft_medkit(self, player, cost: int = 3, healing: float = 35.0) -> bool:
        """Craft a field dressing from scavenged zombie scrap."""
        if self.scrap < cost or player.hp >= player.max_hp:
            return False
        self.scrap -= cost
        player.hp = min(player.max_hp, player.hp + healing)
        return True

    @property
    def battery_percent(self) -> int:
        return int(round(self.flashlight_battery))

    @property
    def stamina_percent(self) -> int:
        return int(round(self.stamina))
