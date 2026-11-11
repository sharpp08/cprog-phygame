"""Collision utilities: grid blocks and circle-vs-grid resolution.

The world is a square grid of blocks (see :mod:`config` for the block codes).
Entities are circles in world space.  :meth:`GridMap.resolve_circle` pushes a
circle out of every blocked tile it overlaps (iteratively), which yields
correct "slide along walls" behaviour for the player and the zombies.
"""
from __future__ import annotations

import math
from typing import List, Sequence

import config


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def distance2(ax: float, ay: float, bx: float, by: float) -> float:
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy


class GridMap:
    """Holds a square block grid and helper queries.

    ``blocks`` is a list of rows (y) of columns (x).  Each tile (tx, ty) is
    treated as the box ``[tx, tx+1) x [ty, ty+1)`` in world space.  Anything
    outside the grid is considered solid so entities can never leave the map.
    """

    def __init__(self, blocks: Sequence[Sequence[int]]) -> None:
        self.blocks = [list(row) for row in blocks]
        self.h = len(self.blocks)
        self.w = len(self.blocks[0]) if self.h else 0

    # -- tile queries -----------------------------------------------------
    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.w and 0 <= ty < self.h

    def is_blocked(self, tx: int, ty: int) -> bool:
        """True when the tile blocks ground movement."""
        if not self.in_bounds(tx, ty):
            return True
        return self.blocks[ty][tx] != config.BLOCK_NONE

    # -- continuous resolution -------------------------------------------
    def resolve_circle(self, pos: Sequence[float], radius: float,
                       iters: int = 4) -> List[float]:
        """Correct ``pos`` so the circle no longer overlaps any blocked tile.

        Pushes the circle out along the minimal penetration vector, iterating
        a few times so corner cases (two tiles at once) resolve cleanly.
        """
        cx, cy = pos[0], pos[1]
        for _ in range(iters):
            moved = False
            tx0 = int(math.floor(cx - radius))
            tx1 = int(math.floor(cx + radius))
            ty0 = int(math.floor(cy - radius))
            ty1 = int(math.floor(cy + radius))
            for ty in range(ty0, ty1 + 1):
                for tx in range(tx0, tx1 + 1):
                    if not self.is_blocked(tx, ty):
                        continue
                    nx = clamp(cx, tx, tx + 1)
                    ny = clamp(cy, ty, ty + 1)
                    dx = cx - nx
                    dy = cy - ny
                    d2 = dx * dx + dy * dy
                    if d2 >= radius * radius:
                        continue
                    if d2 > 1e-9:
                        d = math.sqrt(d2)
                        push = (radius - d) / d
                        cx += dx * push
                        cy += dy * push
                    else:
                        # centre is inside the tile: exit through the nearest face
                        pen_left = cx - tx
                        pen_right = (tx + 1) - cx
                        pen_top = cy - ty
                        pen_bottom = (ty + 1) - cy
                        m = min(pen_left, pen_right, pen_top, pen_bottom)
                        if m == pen_left:
                            cx = tx - radius
                        elif m == pen_right:
                            cx = tx + 1 + radius
                        elif m == pen_top:
                            cy = ty - radius
                        else:
                            cy = ty + 1 + radius
                    moved = True
            if not moved:
                break
        return [cx, cy]

    def move_circle(self, pos: Sequence[float], delta: Sequence[float],
                    radius: float) -> List[float]:
        """Move a circle by ``delta`` and resolve against the grid.

        Splits the move into sub-steps so fast objects do not tunnel through
        thin walls between frames.
        """
        nx, ny = pos[0] + delta[0], pos[1] + delta[1]
        dist = math.hypot(nx - pos[0], ny - pos[1])
        steps = max(1, int(math.ceil(dist / (radius * 0.5))))
        steps = min(steps, 8)
        sx, sy = delta[0] / steps, delta[1] / steps
        cur = [float(pos[0]), float(pos[1])]
        for _ in range(steps):
            nxt = [cur[0] + sx, cur[1] + sy]
            cur = self.resolve_circle(nxt, radius, iters=3)
        return cur

    def find_clear_tile(self, near: Sequence[float]) -> Sequence[int]:
        """Return the nearest walkable tile to ``near`` (spiral search)."""
        cx, cy = int(round(near[0])), int(round(near[1]))
        if not self.is_blocked(cx, cy):
            return cx, cy
        for r in range(1, max(self.w, self.h)):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if abs(dx) == r or abs(dy) == r:
                        if not self.is_blocked(cx + dx, cy + dy):
                            return cx + dx, cy + dy
        return cx, cy
