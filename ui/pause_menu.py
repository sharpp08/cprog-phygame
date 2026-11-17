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
        overlay.fill((3, 8, 8, 205))
        screen.blit(overlay, (0, 0))
        panel = pygame.Rect(self.W//2 - 205, self.H//2 - 205, 410, 420)
        pygame.draw.rect(screen, (8, 16, 15), panel, border_radius=8)
        pygame.draw.rect(screen, (85, 105, 85), panel, 1, border_radius=8)
        pygame.draw.line(screen, (177, 145, 91), (panel.x + 28, panel.y + 72), (panel.right - 28, panel.y + 72), 2)
        text(screen, fonts, "FIELD PAUSED", self.W // 2, panel.y + 38, 38, (224, 211, 174), "center", True)
        text(screen, fonts, "Take a breath. The forest is still out there.", self.W // 2, panel.y + 94, 16, (145, 164, 145), "center")
        for _, b in self.buttons:
            b.draw(screen, fonts)
