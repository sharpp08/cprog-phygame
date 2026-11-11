"""Atmospheric lighting: ambient darkness, radial light sources, color grade.

The technique is cheap and GPU-friendly: we build a full-screen dark overlay
each frame, then punch soft holes around light sources with precomputed radial
gradients (cached).  Directional sun shadows are baked into the sprite art and
contact shadows drawn by the renderer, so this module only handles the
ambient "glow in the dark" mood.
"""
from __future__ import annotations

from typing import List, Tuple

import pygame

import config


class Lighting:
    def __init__(self) -> None:
        self._hole_cache: dict = {}
        self.darkness = config.NIGHT_DARKNESS

    # ------------------------------------------------------------------
    def _hole(self, radius: int, strength: float) -> pygame.Surface:
        """Cached radial 'light' sprite: opaque centre fading to the edges.

        Using numpy keeps generation fast even for large radii.
        """
        radius = max(4, int(radius))
        key = (radius, round(strength, 2))
        if key in self._hole_cache:
            return self._hole_cache[key]
        import numpy as np
        size = radius * 2
        yy, xx = np.mgrid[0:size, 0:size]
        dist = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2)
        fall = np.clip(1.0 - dist / radius, 0.0, 1.0)
        fall = fall ** 1.6
        alpha = (fall * strength * 255).astype(np.uint8)
        spr_arr = np.zeros((size, size, 4), dtype=np.uint8)
        spr_arr[..., 0] = 255
        spr_arr[..., 3] = alpha
        # pygame wants (width, height, channels) -> transpose (y,x,c)->(x,y,c)
        spr = pygame.surfarray.make_surface(spr_arr.transpose(1, 0, 2))
        self._hole_cache[key] = spr
        return spr

    # ------------------------------------------------------------------
    def build_shade(self, screen_w: int, screen_h: int,
                    lights: List[Tuple[float, float, float, float]],
                    grade: Tuple[int, int, int] = (24, 28, 40),
                    enabled: bool = True) -> pygame.Surface:
        """Return the shade overlay to blit over the rendered world.

        ``lights`` is a list of (screen_x, screen_y, world_radius, strength).
        """
        shade = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        if not enabled:
            return shade
        shade.fill((grade[0], grade[1], grade[2], int(self.darkness * 255)))
        for sx, sy, wrad, strength in lights:
            radius = int(wrad * 26) + 40     # approximate world->px radius
            hole = self._hole(radius, strength)
            shade.blit(hole, (int(sx - radius), int(sy - radius)),
                       special_flags=pygame.BLEND_RGBA_SUB)
        return shade
