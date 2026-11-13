"""Weapon model: stats, firing, reloading and recoil per config spec."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import config


class Weapon:
    def __init__(self, kind: str, reserve: int = None) -> None:
        self.kind = kind
        self.spec = config.WEAPONS[kind]
        self.mag_size = self.spec["mag_size"]
        self.mag = self.mag_size
        self.reserve = self.spec["reserve_max"] if reserve is None else reserve
        self.fire_cooldown = 0.0
        self.reloading = False
        self.reload_timer = 0.0
        self.recoil = 0.0
        self.muzzle_timer = 0.0

    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return self.spec["name"]

    @property
    def fire_mode(self) -> str:
        return self.spec["fire_mode"]

    def can_fire(self) -> bool:
        return (self.fire_cooldown <= 0.0 and not self.reloading
                and self.mag > 0)

    def is_empty(self) -> bool:
        return self.mag == 0

    @property
    def reload_progress(self) -> float:
        """Normalised reload animation progress (zero when not reloading)."""
        if not self.reloading:
            return 0.0
        total = max(0.001, float(self.spec["reload_time"]))
        return max(0.0, min(1.0, 1.0 - self.reload_timer / total))

    # ------------------------------------------------------------------
    def try_fire(self) -> Optional[Dict]:
        """Return projectile parameters when a shot can be made, else None.

        The combat system uses this to spawn the actual bullet objects; the
        weapon only owns its internal timers/ammo so it stays headless.
        """
        if not self.can_fire():
            return None
        self.mag -= 1
        self.fire_cooldown = 1.0 / self.spec["fire_rate"]
        self.recoil = min(1.0, self.recoil + self.spec["recoil"])
        self.muzzle_timer = 0.06
        return {
            "damage": self.spec["damage"],
            "speed": self.spec["bullet_speed"],
            "range": self.spec["range"],
            "spread": self.spec["spread"],
            "pellets": self.spec["pellets"],
            "ammo": self.spec["ammo_type"],
            "kind": self.kind,
        }

    # ------------------------------------------------------------------
    def start_reload(self) -> bool:
        if self.reloading or self.mag == self.mag_size or self.reserve <= 0:
            return False
        self.reloading = True
        self.reload_timer = self.spec["reload_time"]
        return True

    def update(self, dt: float) -> None:
        if self.fire_cooldown > 0:
            self.fire_cooldown -= dt
        if self.muzzle_timer > 0:
            self.muzzle_timer -= dt
        if self.recoil > 0:
            self.recoil = max(0.0, self.recoil - 3.0 * dt)
        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0:
                need = self.mag_size - self.mag
                take = min(need, self.reserve)
                self.mag += take
                self.reserve -= take
                self.reloading = False

    def add_reserve(self, amount: int) -> None:
        self.reserve = min(self.spec["reserve_max"], self.reserve + amount)

    def ammo_name(self) -> str:
        return f"ammo_{self.spec['ammo_type']}"

    def to_dict(self) -> Dict:
        return {"kind": self.kind, "mag": self.mag, "reserve": self.reserve}

    @classmethod
    def from_dict(cls, d: Dict) -> "Weapon":
        w = cls(d["kind"])
        w.mag = d.get("mag", w.mag_size)
        w.reserve = d.get("reserve", w.reserve)
        return w
