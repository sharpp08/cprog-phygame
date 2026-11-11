"""Isometric camera: smooth tracking, zoom, bounds and projection helpers.

The camera keeps a world-space focus point centred on the screen.  Because the
iso plane is rotated 45 degrees, converting between screen and world needs the
special 2x2 system solved here -- see :meth:`screen_to_world`, which is what
makes mouse aiming accurate.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import config


class Camera:
    def __init__(self, screen_w: int, screen_h: int,
                 zoom: float = config.CAM_DEFAULT_ZOOM) -> None:
        self.sw = screen_w
        self.sh = screen_h
        self.zoom = float(zoom)
        self.fx = 0.0
        self.fy = 0.0
        self.fz = 0.0
        self._minx = self._miny = 0.0
        self._maxx = self._maxy = config.MAP_W

    # ------------------------------------------------------------------
    def set_size(self, w: int, h: int) -> None:
        self.sw = w
        self.sh = h

    def set_zoom(self, z: float) -> None:
        self.zoom = min(config.CAM_MAX_ZOOM,
                        max(config.CAM_MIN_ZOOM, z))

    def set_bounds(self, minx: float, miny: float,
                   maxx: float, maxy: float) -> None:
        m = config.CAM_MARGIN
        self._minx = minx + m
        self._miny = miny + m
        self._maxx = maxx - m
        self._maxy = maxy - m
        self._clamp()

    def _clamp(self) -> None:
        self.fx = min(max(self.fx, self._minx), self._maxx)
        self.fy = min(max(self.fy, self._miny), self._maxy)

    def snap(self, target_x: float, target_y: float) -> None:
        """Jump immediately to a target (used when loading a save)."""
        self.fx = target_x
        self.fy = target_y
        self._clamp()

    # ------------------------------------------------------------------
    def world_to_screen(self, x: float, y: float, z: float = 0.0) -> Tuple[float, float]:
        sx = (x - y - self.fx + self.fy) * config.SCALE_X * self.zoom + self.sw / 2.0
        sy = (x + y - self.fx - self.fy) * config.SCALE_Y * self.zoom \
            - z * config.HEIGHT_SCALE * self.zoom + self.sh / 2.0
        return sx, sy

    def screen_to_world(self, sx: float, sy: float, z: float = 0.0) -> Tuple[float, float]:
        a = (sx - self.sw / 2.0) / (config.SCALE_X * self.zoom)
        b = (sy - self.sh / 2.0 + z * config.HEIGHT_SCALE * self.zoom) / \
            (config.SCALE_Y * self.zoom)
        x = self.fx + (a + b) / 2.0
        y = self.fy + (b - a) / 2.0
        return x, y

    # ------------------------------------------------------------------
    def cull_bounds(self, pad: float = 1.5) -> Tuple[float, float, float, float]:
        """Conservative world-space bounding box currently on screen."""
        corners = [
            self.screen_to_world(0, 0),
            self.screen_to_world(self.sw, 0),
            self.screen_to_world(0, self.sh),
            self.screen_to_world(self.sw, self.sh),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

    def scale(self, value: float) -> float:
        """Scale a world/length value by the current camera zoom."""
        return value * self.zoom

    # -- aliases used by the renderer / game loop ---------------------
    def iso_to_screen(self, x: float, y: float, z: float = 0.0):
        return self.world_to_screen(x, y, z)

    def set_target(self, x: float, y: float) -> None:
        self.snap(x, y)

    def clamp(self, minx: float, miny: float, maxx: float,
              maxy: float) -> None:
        self.set_bounds(minx, miny, maxx, maxy)

    def update(self, dt, target_x=None, target_y=None) -> None:
        """Smooth follow.  ``target`` is optional so legacy one-arg calls
        still work (reuses the last focus point)."""
        if target_x is None:
            target_x, target_y = self.fx, self.fy
        t = 1.0 - math.exp(-config.CAM_FOLLOW_SMOOTH * dt)
        self.fx += (target_x - self.fx) * t
        self.fy += (target_y - self.fy) * t
        self._clamp()
