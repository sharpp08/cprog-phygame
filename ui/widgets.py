"""Reusable screen-space widgets: buttons, sliders and text helpers."""
from __future__ import annotations

import pygame


class FontSet:
    """Cached fonts by size."""

    def __init__(self) -> None:
        self._cache: dict = {}

    def get(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key not in self._cache:
            f = pygame.font.Font(None, size)
            f.set_bold(bold)
            self._cache[key] = f
        return self._cache[key]


def text(screen, fonts: FontSet, s: str, x: int, y: int, size: int,
         color=(235, 230, 215), align: str = "left",
         bold: bool = False) -> None:
    f = fonts.get(size, bold)
    surf = f.render(s, True, color)
    r = surf.get_rect()
    if align == "center":
        r.center = (x, y)
    elif align == "right":
        r.midright = (x, y)
    else:
        r.midleft = (x, y)
    screen.blit(surf, r)


class Button:
    def __init__(self, label: str, x: int, y: int, w: int, h: int,
                 action) -> None:
        self.label = label
        self.rect = pygame.Rect(x, y, w, h)
        self.action = action
        self.enabled = True

    def handle(self, event, screen, fonts: FontSet, audio=None) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.enabled:
                if audio:
                    audio.play("ui")
                self.action()
        elif event.type == pygame.MOUSEMOTION:
            pass

    def draw(self, screen, fonts: FontSet) -> None:
        hovered = self.rect.collidepoint(pygame.mouse.get_pos()) \
            and self.enabled
        col = (46, 42, 34) if hovered else (30, 27, 22)
        border = (190, 170, 110) if hovered else (70, 64, 54)
        pygame.draw.rect(screen, col, self.rect, border_radius=8)
        pygame.draw.rect(screen, border, self.rect, 2, border_radius=8)
        text(screen, fonts, self.label, self.rect.centerx,
             self.rect.centery, 24, (240, 235, 220), "center", True)


class Slider:
    def __init__(self, label: str, x: int, y: int, w: int,
                 value: float, vmin: float, vmax: float, step: float,
                 on_change) -> None:
        self.label = label
        self.x = x
        self.y = y
        self.w = w
        self.value = value
        self.vmin = vmin
        self.vmax = vmax
        self.step = step
        self.on_change = on_change
        self.dragging = False
        self.track = pygame.Rect(x, y + 18, w, 8)

    def handle(self, event, screen, fonts: FontSet) -> None:
        mx = event.pos[0] if event.type in (pygame.MOUSEMOTION,
                                            pygame.MOUSEBUTTONDOWN) \
            else None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.track.inflate(0, 14).collidepoint(event.pos):
                self.dragging = True
                self._set(mx)
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._set(mx)

    def _set(self, mx) -> None:
        if mx is None:
            return
        t = (mx - self.track.x) / self.track.w
        t = max(0.0, min(1.0, t))
        raw = self.vmin + t * (self.vmax - self.vmin)
        val = round(round((raw - self.vmin) / self.step) * self.step
                    + self.vmin, 3)
        if val != self.value:
            self.value = val
            self.on_change(val)

    def draw(self, screen, fonts: FontSet) -> None:
        text(screen, fonts, f"{self.label}: {self.value:g}", self.x,
             self.y, 20, (200, 195, 180))
        pygame.draw.rect(screen, (55, 50, 42), self.track,
                         border_radius=4)
        t = (self.value - self.vmin) / (self.vmax - self.vmin)
        fill_w = int(self.track.w * t)
        pygame.draw.rect(screen, (190, 160, 90),
                         (self.track.x, self.track.y, fill_w, 8),
                         border_radius=4)
        knob_x = self.track.x + fill_w
        pygame.draw.circle(screen, (240, 225, 180), (knob_x,
                                                     self.track.centery),
                           9)
