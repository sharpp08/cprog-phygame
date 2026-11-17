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
        hovered = self.rect.collidepoint(pygame.mouse.get_pos()) and self.enabled
        if not self.enabled:
            fill, edge, ink = (15, 20, 19), (38, 48, 43), (82, 94, 84)
        elif hovered:
            fill, edge, ink = (49, 54, 43), (205, 177, 116), (250, 237, 207)
        else:
            fill, edge, ink = (18, 27, 25), (86, 104, 88), (218, 219, 194)
        pygame.draw.rect(screen, (3, 7, 7), self.rect.move(0, 3), border_radius=5)
        pygame.draw.rect(screen, fill, self.rect, border_radius=5)
        pygame.draw.rect(screen, edge, self.rect, 1, border_radius=5)
        accent_h = self.rect.h - 16 if hovered else self.rect.h - 24
        pygame.draw.line(screen, (176, 143, 88) if hovered else (88, 103, 83),
                         (self.rect.x + 10, self.rect.centery - accent_h//2),
                         (self.rect.x + 10, self.rect.centery + accent_h//2), 2)
        text(screen, fonts, self.label, self.rect.centerx + 4,
             self.rect.centery, 22, ink, "center", True)
        if hovered:
            pygame.draw.line(screen, (191, 161, 105),
                             (self.rect.x + 20, self.rect.bottom - 4),
                             (self.rect.right - 12, self.rect.bottom - 4), 2)



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
