"""Main menu: title, New Game / Continue / Settings / Exit."""
from __future__ import annotations

from typing import Optional

import pygame

from ui.widgets import Button, FontSet, text


class MainMenu:
    def __init__(self, w: int, h: int, has_save: bool) -> None:
        self.W = w
        self.H = h
        self.fonts = FontSet()
        cx = w // 2
        bw, bh, gap = 260, 52, 78
        y0 = h // 2 - 30
        self.buttons = [
            ("New Game", Button("New Game", cx - bw // 2, y0, bw, bh,
                                lambda: None)),
            ("Continue", Button("Continue", cx - bw // 2, y0 + gap, bw, bh,
                                lambda: None)),
            ("Settings", Button("Settings", cx - bw // 2, y0 + 2 * gap, bw,
                                bh, lambda: None)),
            ("Exit", Button("Exit", cx - bw // 2, y0 + 3 * gap, bw, bh,
                            lambda: None)),
        ]
        self.buttons[1][1].enabled = has_save

    # ------------------------------------------------------------------
    def handle(self, event, audio=None) -> Optional[str]:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, b in self.buttons:
                if b.enabled and b.rect.collidepoint(event.pos):
                    if audio:
                        audio.play("ui")
                    return self._action(name)
        return None

    @staticmethod
    def _action(name: str) -> str:
        return {"New Game": "start", "Continue": "continue",
                "Settings": "settings", "Exit": "exit"}[name]

    # ------------------------------------------------------------------
    def draw(self, screen, fonts: FontSet) -> None:
        f = self.fonts
        text(screen, f, "WHEN THE WOODS BLEED", self.W // 2, self.H // 4, 64,
             (240, 210, 120), "center", True)
        text(screen, f, "Isometric Zombie Survival Horror", self.W // 2,
             self.H // 4 + 56, 26, (190, 180, 150), "center")
        for _, b in self.buttons:
            b.draw(screen, fonts)
