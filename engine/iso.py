"""Isometric 2.5D projection math.

Pure, framework-free functions so they can be unit-tested without a display.
World space is a continuous (x, y, z) grid: x and y are horizontal "tile"
coordinates, z is height above the ground. The projection is the classic
2:1 diamond mapping configured in :mod:`config`.
"""
from __future__ import annotations

from typing import Tuple

import config


def project(wx: float, wy: float, wz: float = 0.0) -> Tuple[float, float]:
    """World -> unprojected screen coordinates (camera offset not applied)."""
    sx = (wx - wy) * config.SCALE_X
    sy = (wx + wy) * config.SCALE_Y - wz * config.HEIGHT_SCALE
    return sx, sy


def unproject(sx: float, sy: float, wz: float = 0.0) -> Tuple[float, float]:
    """Inverse of :func:`project` (camera offset not applied).

    Solves the 2x2 system for world x/y given a screen point on the plane
    z = ``wz``.
    """
    sx_ = sx / config.SCALE_X
    sy_ = (sy + wz * config.HEIGHT_SCALE) / config.SCALE_Y
    wx = (sx_ + sy_) / 2.0
    wy = (sy_ - sx_) / 2.0
    return wx, wy


def depth(wx: float, wy: float) -> float:
    """Depth sort key: larger values render later (closer to viewer)."""
    return wx + wy


def screen_direction_aim(player: Tuple[float, float], aim: Tuple[float, float]) -> Tuple[float, float]:
    """Normalised 2D world-space direction from ``player`` to ``aim``.

    This is the correct way to aim in an isometric game: the on-screen cursor
    is converted to a world point first, then a world-space direction is
    derived. Using raw screen deltas would be wrong because the iso plane is
    rotated 45 degrees relative to the screen.
    """
    dx = aim[0] - player[0]
    dy = aim[1] - player[1]
    m = (dx * dx + dy * dy) ** 0.5
    if m < 1e-6:
        return 0.0, 0.0
    return dx / m, dy / m


def tile_corners(tx: float, ty: float):
    """Return the four screen corners (N, E, S, W) of a unit diamond tile."""
    # Corner of tile at the start of the diamond, offset to cover it.
    p = project(tx, ty)
    return (
        (p[0], p[1]),                                   # top
        (p[0] + config.SCALE_X, p[1] + config.SCALE_Y),   # right
        (p[0], p[1] + config.TILE_H),                     # bottom
        (p[0] - config.SCALE_X, p[1] + config.SCALE_Y),   # left
    )
