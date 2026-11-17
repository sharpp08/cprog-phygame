"""Cinematic loading transition for WHEN THE WOODS BLEED."""
from __future__ import annotations

import math
import random
import pygame

from ui.widgets import FontSet, text


class LoadingScreen:
    """Animated, self-contained loading interstitial with a forest silhouette."""

    TIPS = (
        "Keep your flashlight charged. Darkness hides more than the path.",
        "Gunfire travels far through the forest. Every shot has a cost.",
        "Crouch to move quietly when infected are close.",
        "Scrap can be turned into a medkit. Save supplies for the shrine.",
        "Listen carefully. The forest often warns you before it attacks.",
    )

    def __init__(self, w: int, h: int) -> None:
        self.W, self.H = w, h
        self.fonts = FontSet()
        self.started = 0
        self._stars = [(random.Random(i).randrange(w),
                        random.Random(i + 200).randrange(max(1, h // 2)),
                        random.Random(i + 400).uniform(0.5, 1.8))
                       for i in range(46)]
        self._tree_layers = []
        rng = random.Random(71)
        for layer, count in ((0, 13), (1, 18), (2, 25)):
            trees = []
            for _ in range(count):
                x = rng.randrange(-40, w + 40)
                height = rng.randrange(int(h * (0.20 + layer * 0.035)),
                                       int(h * (0.36 + layer * 0.055)))
                width = rng.randrange(24, 58)
                trees.append((x, height, width))
            self._tree_layers.append(trees)

    def draw(self, screen, elapsed: float, message: str = "PREPARING THE FOREST") -> None:
        w, h = screen.get_size()
        screen.fill((5, 9, 10))
        # Cold night-sky gradient.
        for y in range(h):
            t = y / max(1, h)
            col = (int(7 + 10 * t), int(13 + 11 * t), int(17 + 8 * t))
            pygame.draw.line(screen, col, (0, y), (w, y))
        # Moon and distant haze.
        moon = (int(w * 0.77), int(h * 0.27))
        glow = pygame.Surface((190, 190), pygame.SRCALPHA)
        for radius, alpha in ((88, 5), (64, 9), (42, 16)):
            pygame.draw.circle(glow, (177, 190, 158, alpha),
                               (95, 95), radius)
        screen.blit(glow, (moon[0] - 95, moon[1] - 95))
        pygame.draw.circle(screen, (176, 185, 157), moon, max(13, h // 34))
        pygame.draw.circle(screen, (119, 135, 119),
                           (moon[0] + 9, moon[1] - 6), max(3, h // 130))
        # Stars and slow drifting mist.
        for x, y, speed in self._stars:
            twinkle = 110 + int(80 * abs(math.sin(elapsed * speed + x)))
            screen.set_at((x, y), (twinkle, twinkle, max(0, twinkle - 18)))
        mist = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(4):
            x = int((elapsed * (12 + i * 5) + i * w * 0.31) % (w + 260)) - 130
            y = int(h * (0.48 + i * 0.075))
            pygame.draw.ellipse(mist, (126, 145, 132, 13),
                                (x - 190, y - 28, 380, 72))
        screen.blit(mist, (0, 0))
        # Layered forest silhouettes.
        for layer, trees in enumerate(self._tree_layers):
            base = int(h * (0.78 + layer * 0.075))
            color = ((13, 24, 23), (9, 17, 17), (5, 10, 11))[layer]
            drift = int(elapsed * (3 + layer * 2))
            for x, th, tw in trees:
                px = (x - drift * (layer + 1)) % (w + 100) - 50
                pygame.draw.rect(screen, color,
                                 (px - max(2, tw // 9), base - th // 3,
                                  max(4, tw // 4), th // 3 + 8))
                pygame.draw.polygon(screen, color,
                    [(px, base - th), (px - tw // 2, base - th // 3),
                     (px - tw // 4, base - th // 3),
                     (px - tw // 2, base), (px + tw // 2, base),
                     (px + tw // 4, base - th // 3),
                     (px + tw // 2, base - th // 3)])
        # Centered title treatment.
        title_y = int(h * 0.43)
        text(screen, self.fonts, "WHEN THE WOODS BLEED", w // 2,
             title_y, max(34, min(62, w // 19)), (221, 207, 160), "center", True)
        text(screen, self.fonts, "THE FOREST REMEMBERS", w // 2,
             title_y + 38, 17, (126, 145, 131), "center", True)
        # Loading indicator and subtle animated segments.
        bar_w = min(390, int(w * 0.42))
        bar_h = 5
        bx, by = (w - bar_w) // 2, int(h * 0.83)
        pygame.draw.rect(screen, (39, 48, 44), (bx, by, bar_w, bar_h),
                         border_radius=3)
        progress = 0.22 + 0.72 * (0.5 + 0.5 * math.sin(elapsed * 1.15 - 1.2))
        pygame.draw.rect(screen, (177, 151, 96),
                         (bx, by, int(bar_w * progress), bar_h),
                         border_radius=3)
        text(screen, self.fonts, message, w // 2, by - 22, 16,
             (186, 184, 157), "center", True)
        tip = self.TIPS[int(elapsed // 4) % len(self.TIPS)]
        text(screen, self.fonts, tip, w // 2, h - 30, 16,
             (133, 147, 133), "center")
