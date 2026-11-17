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
        overlay.fill((3, 7, 7, 220))
        screen.blit(overlay, (0, 0))
        panel = pygame.Rect(self.W//2 - 310, self.H//2 - 205, 620, 440)
        pygame.draw.rect(screen, (8, 17, 15), panel, border_radius=8)
        pygame.draw.rect(screen, (83, 102, 80), panel, 1, border_radius=8)
        pygame.draw.line(screen, (177, 145, 91), (panel.x + 36, panel.y + 82), (panel.right - 36, panel.y + 82), 2)
        f = self.fonts
        if won:
            title = self.ending_title or "You Escaped"
            text(screen, f, title, self.W // 2, panel.y + 48, 48,
                 (180, 220, 120), "center", True)
            sub = self.ending_subtitle or "The forest falls silent behind you."
        else:
            text(screen, f, "YOU DIED", self.W // 2, panel.y + 48, 58,
                 (200, 83, 62), "center", True)
            sub = "The forest reclaims another soul."
        text(screen, f, sub, self.W // 2, panel.y + 112, 21,
             (200, 190, 170), "center")
        text(screen, f, f"Score {score}    Kills {kills}    "
             f"Time {int(time_s // 60)}:{int(time_s % 60):02d}",
             self.W // 2, panel.y + 208, 22, (230, 220, 200), "center",
             True)
        for _, b in self.buttons:
            b.draw(screen, fonts)
