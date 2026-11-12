"""Cached low-resolution lighting and atmospheric post effects.

This module deliberately stays in Pygame's software-surface pipeline. It
builds expensive radial/vignette textures once, then reuses fixed-size
surfaces so the renderer does not allocate full-screen NumPy arrays every
frame. Quality levels: 0=low, 1=medium, 2=high.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pygame

import config


class VisualEnhancement:
    def __init__(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self._lw = max(1, self.width // 4)
        self._lh = max(1, self.height // 4)
        self._shade = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._shade_full = pygame.Surface((self.width, self.height),
                                          pygame.SRCALPHA)
        self._beam = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._fog = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._fog_full = pygame.Surface((self.width, self.height),
                                        pygame.SRCALPHA)
        self._vignette = self._build_vignette()
        self._grain = self._build_grain()
        self._radials: dict[int, pygame.Surface] = {}
        self._last_size = (self.width, self.height)

    def resize(self, width: int, height: int) -> None:
        size = (max(1, int(width)), max(1, int(height)))
        if size == self._last_size:
            return
        self.__init__(*size)

    def _build_vignette(self) -> pygame.Surface:
        w, h = self.width, self.height
        yy, xx = np.mgrid[0:h, 0:w]
        nx = (xx - w * 0.5) / max(1.0, w * 0.5)
        ny = (yy - h * 0.5) / max(1.0, h * 0.5)
        radius = np.sqrt(nx * nx + ny * ny)
        alpha = np.clip((radius - 0.30) / 0.78, 0.0, 1.0) ** 1.7
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0] = 1
        rgba[..., 1] = 3
        rgba[..., 2] = 9
        rgba[..., 3] = (alpha * 112).astype(np.uint8)
        return pygame.image.frombuffer(rgba.tobytes(), (w, h),
                                       "RGBA").convert_alpha()

    def _build_grain(self) -> pygame.Surface:
        rng = np.random.default_rng(731)
        rgba = np.zeros((96, 96, 4), dtype=np.uint8)
        values = rng.integers(90, 240, size=(96, 96), dtype=np.uint8)
        rgba[..., 0] = values
        rgba[..., 1] = values
        rgba[..., 2] = values
        rgba[..., 3] = rng.integers(0, 14, size=(96, 96), dtype=np.uint8)
        return pygame.image.frombuffer(rgba.tobytes(), (96, 96),
                                       "RGBA").convert_alpha()

    def _radial(self, radius: int) -> pygame.Surface:
        radius = max(8, min(220, int(radius)))
        cached = self._radials.get(radius)
        if cached is not None:
            return cached
        size = radius * 2
        yy, xx = np.mgrid[0:size, 0:size]
        dist = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2)
        falloff = np.clip(1.0 - dist / radius, 0.0, 1.0) ** 1.65
        rgba = np.zeros((size, size, 4), dtype=np.uint8)
        rgba[..., 3] = (falloff * 210).astype(np.uint8)
        radial = pygame.image.frombuffer(rgba.tobytes(), (size, size),
                                         "RGBA").convert_alpha()
        self._radials[radius] = radial
        return radial

    def apply_lighting(self, screen: pygame.Surface, cam, world,
                       player, quality: int) -> None:
        """Apply cool night ambience and cached radial light falloff."""
        if quality <= 0:
            alpha = 48
        elif quality == 1:
            alpha = 76
        else:
            alpha = 94
        self._shade.fill((4, 8, 19, alpha))
        zoom = max(0.4, float(cam.zoom))
        lights = []
        for wx, wy, radius, intensity in getattr(world, "lights", ()):
            sx, sy = cam.iso_to_screen(wx, wy, 0.0)
            lights.append((sx / 4.0, sy / 4.0,
                           radius * 32.0 * zoom / 4.0,
                           max(0.0, min(1.0, float(intensity)))))
        if player is not None:
            sx, sy = cam.iso_to_screen(player.x, player.y, 0.0)
            # Focused flashlight pool: a soft centre and a fast outer falloff.
            lights.append((sx / 4.0, sy / 4.0,
                           7.4 * 32.0 * zoom / 4.0, 0.92))
            if quality >= 1:
                aim_x, aim_y = getattr(player, "aim", (1.0, 0.0))
                dx = (aim_x - aim_y) * config.SCALE_X
                dy = (aim_x + aim_y) * config.SCALE_Y
                length = math.hypot(dx, dy) or 1.0
                dx, dy = dx / length, dy / length
                radius = 9.0 * 32.0 * zoom / 4.0
                ox, oy = sx / 4.0, sy / 4.0
                ex, ey = ox + dx * radius, oy + dy * radius
                px, py = -dy * radius * 0.34, dx * radius * 0.34
                self._beam.fill((0, 0, 0, 0))
                pygame.draw.polygon(
                    self._beam, (0, 0, 0, 42),
                    [(int(ox), int(oy)), (int(ex + px), int(ey + py)),
                     (int(ex - px), int(ey - py))])
                pygame.draw.polygon(
                    self._beam, (0, 0, 0, 24),
                    [(int(ox), int(oy)), (int(ox + dx * radius),
                                          int(oy + dy * radius)),
                     (int(ox + dx * radius * 0.88 + px * 0.55),
                      int(oy + dy * radius * 0.88 + py * 0.55))])
        for lx, ly, radius, strength in lights:
            r = max(8, min(220, int(radius)))
            radial = self._radial(r)
            radial.set_alpha(int(255 * strength))
            self._shade.blit(radial, (int(lx - r), int(ly - r)),
                             special_flags=pygame.BLEND_RGBA_SUB)
        if player is not None and quality >= 1:
            self._shade.blit(self._beam, (0, 0),
                             special_flags=pygame.BLEND_RGBA_SUB)
        pygame.transform.scale(self._shade, (self.width, self.height),
                               self._shade_full)
        screen.blit(self._shade_full, (0, 0))
        screen.blit(self._vignette, (0, 0))

    def draw_atmosphere(self, screen: pygame.Surface, cam, world,
                        time_value: float, quality: int) -> None:
        if quality < 1:
            return
        self._fog.fill((0, 0, 0, 0))
        # Low, slow-moving ground mist; screen-space puffs are intentionally
        # broad and subtle so they never obscure the player or UI.
        strength = 18 if quality == 1 else 27
        for i in range(5 if quality == 1 else 8):
            phase = time_value * (0.10 + i * 0.009) + i * 1.73
            x = int((0.5 + 0.42 * math.sin(phase)) * self._lw)
            y = int((0.58 + 0.25 * math.sin(phase * 0.71 + i)) * self._lh)
            rx = 22 + (i % 3) * 9
            ry = 5 + (i % 2) * 3
            color = (115, 139, 157, strength)
            pygame.draw.ellipse(self._fog, color,
                                (x - rx, y - ry, rx * 2, ry * 2))
            pygame.draw.ellipse(self._fog, (145, 164, 176, strength // 2),
                                (x - rx // 2, y - ry - 2, rx, ry * 2))
        pygame.transform.scale(self._fog, (self.width, self.height),
                               self._fog_full)
        screen.blit(self._fog_full, (0, 0))
        if quality >= 2:
            screen.blit(self._grain, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            screen.blit(self._grain, (self.width - 96, self.height - 96),
                        special_flags=pygame.BLEND_RGBA_ADD)
