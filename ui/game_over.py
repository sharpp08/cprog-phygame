"""End-of-game screen for both victory and defeat."""
from __future__ import annotations

from typing import Optional

import pygame

from ui.widgets import Button, FontSet, text


class GameOver:
    def __init__(self, w: int, h: int) -> None:
        self.W = w
        self.H = h
        self.fonts = FontSet()
        self.ending_title = None
        self.ending_subtitle = None
        cx = w // 2
        y0 = h // 2 + 60
        self.buttons = [
            ("Play Again", Button("Play Again", cx - 260, y0, 240, 54,
                                  lambda: None)),
            ("Main Menu", Button("Main Menu", cx + 20, y0, 240, 54,
                                 lambda: None)),
        ]

    def handle(self, event, audio=None) -> Optional[str]:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, b in self.buttons:
                if b.rect.collidepoint(event.pos):
                    if audio:
                        audio.play("ui")
                    return "restart" if name == "Play Again" else "main_menu"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "main_menu"
        return None

    def draw(self, screen, fonts: FontSet, won: bool, score: int,
             kills: int, time_s: int) -> None:
        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        overlay.fill((8, 6, 4, 200))
        screen.blit(overlay, (0, 0))
        f = self.fonts
        if won:
            title = self.ending_title or "You Escaped"
            text(screen, f, title, self.W // 2, self.H // 4, 58,
                 (180, 220, 120), "center", True)
            sub = self.ending_subtitle or "The forest falls silent behind you."
        else:
            text(screen, f, "You Died", self.W // 2, self.H // 4, 72,
                 (200, 70, 50), "center", True)
            sub = "The forest reclaims another soul."
        text(screen, f, sub, self.W // 2, self.H // 4 + 50, 26,
             (200, 190, 170), "center")
        text(screen, f, f"Score {score}    Kills {kills}    "
             f"Time {int(time_s // 60)}:{int(time_s % 60):02d}",
             self.W // 2, self.H // 2 + 20, 24, (230, 220, 200), "center",
             True)
        for _, b in self.buttons:
            b.draw(screen, fonts)
