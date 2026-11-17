"""Cinematic main menu for the forest survival experience."""
from __future__ import annotations

from typing import Optional
import math
import pygame

from ui.widgets import Button, FontSet, text


class MainMenu:
    def __init__(self, w: int, h: int, has_save: bool) -> None:
        self.W, self.H = w, h
        self.fonts = FontSet()
        bw, bh, gap = min(330, int(w * 0.31)), 54, 13
        x = int(w * 0.105)
        y0 = int(h * 0.49)
        self.buttons = [
            ("New Game", Button("NEW GAME", x, y0, bw, bh, None)),
            ("Continue", Button("CONTINUE", x, y0 + bh + gap, bw, bh, None)),
            ("Settings", Button("SETTINGS", x, y0 + 2 * (bh + gap), bw, bh, None)),
            ("Exit", Button("EXIT", x, y0 + 3 * (bh + gap), bw, bh, None)),
        ]
        self.buttons[1][1].enabled = has_save
        self.has_save = has_save

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

    def draw(self, screen, fonts: FontSet) -> None:
        w, h = screen.get_size()
        t = pygame.time.get_ticks() * 0.001
        # Dark vignette and low forest horizon.
        screen.fill((7, 12, 12))
        for y in range(h):
            q = y / max(1, h)
            pygame.draw.line(screen, (int(9 + 13*q), int(16 + 13*q),
                                      int(18 + 8*q)), (0, y), (w, y))
        moon_x, moon_y = int(w * 0.78), int(h * 0.25)
        halo = pygame.Surface((260, 260), pygame.SRCALPHA)
        pygame.draw.circle(halo, (168, 183, 151, 10), (130, 130), 126)
        pygame.draw.circle(halo, (168, 183, 151, 17), (130, 130), 83)
        screen.blit(halo, (moon_x - 130, moon_y - 130))
        pygame.draw.circle(screen, (156, 169, 145), (moon_x, moon_y),
                           max(19, h // 27))
        # Layered, slow drifting tree silhouettes.
        for layer, count in ((0, 12), (1, 17), (2, 23)):
            base = int(h * (0.72 + layer * 0.09))
            col = ((18, 32, 29), (10, 20, 19), (5, 11, 12))[layer]
            for i in range(count):
                seed = i * 97 + layer * 31
                x = int((seed * 43 + t * (3 + layer * 3)) % (w + 90)) - 45
                tw = 26 + seed % 32
                th = int(h * (0.19 + (seed % 17) / 100 + layer * .025))
                pygame.draw.rect(screen, col, (x - 3, base - th//3, 6, th//3+4))
                pygame.draw.polygon(screen, col,
                    [(x, base-th), (x-tw//2, base-th//3),
                     (x-tw//4, base-th//3), (x-tw//2, base),
                     (x+tw//2, base), (x+tw//4, base-th//3),
                     (x+tw//2, base-th//3)])
        mist = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(3):
            mx = int((t * (11 + i * 5) + i * w * .4) % (w + 300)) - 150
            pygame.draw.ellipse(mist, (135, 153, 136, 12),
                                (mx-180, int(h*(.64+i*.07)), 360, 58))
        screen.blit(mist, (0, 0))
        # Left-aligned identity and menu panel.
        panel = pygame.Surface((int(w*.43), int(h*.77)), pygame.SRCALPHA)
        panel.fill((5, 10, 10, 178))
        screen.blit(panel, (int(w*.055), int(h*.105)))
        left = int(w*.105)
        text(screen, self.fonts, "SURVIVAL  /  HORROR", left, int(h*.19),
             16, (170, 151, 105), "left", True)
        text(screen, self.fonts, "WHEN THE", left, int(h*.265),
             max(38, min(62, w//17)), (223, 215, 185), "left", True)
        text(screen, self.fonts, "WOODS BLEED", left, int(h*.34),
             max(38, min(62, w//17)), (193, 111, 82), "left", True)
        pygame.draw.line(screen, (131, 111, 76),
                         (left, int(h*.405)), (left+min(310,int(w*.28)), int(h*.405)), 2)
        text(screen, self.fonts, "THE FOREST REMEMBERS.", left, int(h*.435),
             18, (164, 176, 155), "left")
        for _, b in self.buttons:
            b.draw(screen, fonts)
        text(screen, self.fonts, "WASD MOVE   •   MOUSE AIM   •   ESC PAUSE",
             int(w*.055), h-22, 14, (104, 124, 112), "left")
        text(screen, self.fonts, "v0.9  /  NIGHTFALL", w-24, h-22, 14,
             (104, 124, 112), "right")
