"""Atomic, validated save/load for player progress.

Save data lives in the per-user writable data directory configured by
``config.SAVE_DIR`` so packaged/read-only installations do not lose progress.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from typing import Optional

import config

SAVE_VERSION = 1
SAVE_FILE = "save.json"


class SaveManager:
    def __init__(self, save_dir: str = config.SAVE_DIR) -> None:
        self.save_dir = os.path.abspath(os.path.expanduser(save_dir))
        os.makedirs(self.save_dir, exist_ok=True)
        self.path = os.path.join(self.save_dir, SAVE_FILE)

    def save(self, player, progression, settings: dict,
             story=None, survival=None) -> bool:
        """Write a complete snapshot atomically; never leave a partial save."""
        data = {
            "version": SAVE_VERSION,
            "world": {"width": config.MAP_W, "height": config.MAP_H},
            "player": player.to_dict(),
            "progression": {
                "phase": progression.phase,
                "state": progression.state,
                "score": progression.score,
                "kills": progression.kills,
                "time": progression.time,
                "wave": progression.wave,
                "shrine_reached": progression.shrine_reached,
                "clues": sorted(story.discovered) if story else [],
            },
            "survival": {
                "stamina": survival.stamina if survival else 100.0,
                "scrap": survival.scrap if survival else 0,
                "flashlight_battery": survival.flashlight_battery if survival else 100.0,
                "flashlight_on": survival.flashlight_on if survival else True,
                "battery_cells": survival.battery_cells if survival else 2,
                "medkits": survival.medkits if survival else 1,
                "grenades": survival.grenades if survival else 2,
            },
            "settings": settings if isinstance(settings, dict) else {},
        }
        temp_path = None
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=self.save_dir,
                    prefix=".save-", suffix=".tmp", delete=False) as handle:
                temp_path = handle.name
                json.dump(data, handle, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            return True
        except (OSError, TypeError, ValueError):
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            return False

    def has_save(self) -> bool:
        return os.path.isfile(self.path)

    def delete(self) -> None:
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass

    def load(self) -> Optional[dict]:
        """Return a structurally valid, resumable save or ``None``."""
        if not os.path.isfile(self.path):
            return None
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            return None
        player = data.get("player")
        progression = data.get("progression")
        if not isinstance(player, dict) or not isinstance(progression, dict):
            return None
        if not all(key in player for key in ("x", "y", "hp", "weapons")):
            return None
        if not isinstance(player.get("weapons"), list):
            return None
        try:
            x, y, hp = (float(player[key]) for key in ("x", "y", "hp"))
            if not all(math.isfinite(value) for value in (x, y, hp)):
                return None
            if hp <= 0:
                return None
        except (TypeError, ValueError):
            return None
        data["settings"] = data.get("settings", {})
        if not isinstance(data["settings"], dict):
            data["settings"] = {}
        data["survival"] = data.get("survival", {})
        if not isinstance(data["survival"], dict):
            data["survival"] = {}
        return data
