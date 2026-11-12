"""Discoverable environmental clues and ending selection."""
from __future__ import annotations

import math


class StorySystem:
    """Small, deterministic clue system tied to existing world landmarks."""

    def __init__(self, world) -> None:
        sx, sy = world.shrine
        rx, ry = world.ruin
        wx, wy = world.waterfall
        start = world.start
        self.clues = [
            {"name": "The missing surveyor", "pos": (start[0] + 2, start[1] - 1),
             "text": "A damp journal: 'The bells ring even when nobody is at the shrine.'"},
            {"name": "The ruined camp", "pos": (rx, ry - 2),
             "text": "A torn field report: 'The infection began beneath the old shrine.'"},
            {"name": "The waterfall marks", "pos": (wx + 2, wy),
             "text": "Scratched into stone: 'Do not let the forest hear your name.'"},
            {"name": "The shrine ledger", "pos": (sx + 2, sy + 1),
             "text": "The final entry: 'The seal needs a living witness to close.'"},
        ]
        self.discovered: set[int] = set()
        self.last_message = ""

    def interact(self, x: float, y: float, radius: float = 2.0):
        choices = [
            (math.hypot(x - clue["pos"][0], y - clue["pos"][1]), i, clue)
            for i, clue in enumerate(self.clues) if i not in self.discovered
        ]
        if not choices:
            return None
        distance, index, clue = min(choices, key=lambda item: item[0])
        if distance > radius:
            return None
        self.discovered.add(index)
        self.last_message = clue["text"]
        return clue

    def ending(self) -> tuple[str, str]:
        count = len(self.discovered)
        if count >= 4:
            return ("THE WITNESS", "You uncover the truth and willingly restore the seal.")
        if count >= 2:
            return ("THE SURVIVOR", "You escape, carrying enough truth to know the forest is not dead.")
        return ("THE ESCAPE", "You survive the shrine, but the forest's secret remains buried.")
