"""Pause menu: resume / settings / restart / main menu."""
from __future__ import annotations

from typing import Optional

import pygame

from ui.widgets import Button, FontSet, text


class PauseMenu:
    def __init__(self, w: int, h: int) -> None:
        self.W = w
        self.H = h
        self.fonts = FontSet()
        cx = w // 2
        bw, bh, gap = 240, 50, 72
        y0 = h // 2 - 100
        self.buttons = [
            ("Resume", Button("Resume", cx - bw // 2, y0, bw, bh, None)),
            ("Settings", Button("Settings", cx - bw // 2, y0 + gap, bw, bh,
                                None)),
            ("Restart", Button("Restart", cx - bw // 2, y0 + 2 * gap, bw,
                               bh, None)),
            ("Main Menu", Button("Main Menu", cx - bw // 2, y0 + 3 * gap,
                                 bw, bh, None)),
        ]

    def handle(self, event, audio=None) -> Optional[str]:
        if event.type == pygame.QUIT:
            return "exit"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if audio:
                audio.play("ui")
            return "resume"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, b in self.buttons:
                if b.rect.collidepoint(event.pos):
                    if audio:
                        audio.play("ui")
                    return {"Resume": "resume", "Settings": "settings",
                            "Restart": "restart",
                            "Main Menu": "main_menu"}[name]
        return None

    def draw(self, screen, fonts: FontSet) -> None:
        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        overlay.fill((10, 8, 6, 170))
        screen.blit(overlay, (0, 0))
        text(screen, fonts, "Paused", self.W // 2, self.H // 4, 64,
             (240, 220, 160), "center", True)
        for _, b in self.buttons:
            b.draw(screen, fonts)
