"""Save / load system.  Persists player, progression and settings as JSON and
refuses to load files that are missing or malformed so a bad save can never
crash the game.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import config

SAVE_VERSION = 1
SAVE_FILE = "save.json"


class SaveManager:
    def __init__(self, save_dir: str = config.SAVE_DIR) -> None:
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.path = os.path.join(save_dir, SAVE_FILE)

    # ------------------------------------------------------------------
    def save(self, player, progression, settings: dict) -> bool:
        data = {
            "version": SAVE_VERSION,
            "player": player.to_dict(),
            "progression": {
                "phase": progression.phase,
                "state": progression.state,
                "score": progression.score,
                "kills": progression.kills,
                "time": progression.time,
                "wave": progression.wave,
                "shrine_reached": progression.shrine_reached,
            },
            "settings": settings,
        }
        try:
            with open(self.path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    def has_save(self) -> bool:
        return os.path.exists(self.path)

    def delete(self) -> None:
        if os.path.exists(self.path):
            os.remove(self.path)

    # ------------------------------------------------------------------
    def load(self) -> Optional[dict]:
        """Return a validated save dict, or None if missing / corrupt."""
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            return None
        if "player" not in data or "progression" not in data:
            return None
        p = data["player"]
        if not all(k in p for k in ("x", "y", "hp", "weapons")):
            return None
        data["settings"] = data.get("settings", {})
        return data
