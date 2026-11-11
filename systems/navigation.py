"""Grid pathfinding and per-zombie navigation.

Zombies follow A* paths so they route around trees, rocks, water and the
shrine instead of walking straight through obstacles.  Paths are cached per
(start,goal) tile pair and re-planned periodically, so 40+ zombies stay cheap.
"""
from __future__ import annotations

import heapq
import math
from typing import List, Optional, Tuple

import config


def _octile(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return max(dx, dy) + 0.41421356 * min(dx, dy)


class Navigation:
    def __init__(self, grid, w: int, h: int) -> None:
        self.grid = grid
        self.w = w
        self.h = h
        self._path_cache: dict = {}
        self._path_cache_size = 0
        self._DIRS = ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
                      (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414),
                      (-1, -1, 1.414))

    def _blocked(self, tile) -> bool:
        return self.grid.is_blocked(tile[0], tile[1])

    # ------------------------------------------------------------------
    def a_star(self, start: Tuple[int, int],
               goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        start = (int(start[0]), int(start[1]))
        goal = (int(goal[0]), int(goal[1]))
        if self.grid.is_blocked(goal[0], goal[1]):
            goal = tuple(self.grid.find_clear_tile(goal))
        if start == goal:
            return [goal]
        cache_key = (start, goal)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        g_score = {start: 0.0}
        came: dict = {}
        open_heap: list = []
        heapq.heappush(open_heap, (_octile(start, goal), 0.0, start))
        closed = {start}
        nodes = 0
        while open_heap and nodes < 1800:
            _, _, cur = heapq.heappop(open_heap)
            if cur == goal:
                path = [cur]
                while cur in came:
                    cur = came[cur]
                    path.append(cur)
                path.reverse()
                self._store(cache_key, path)
                return path
            nodes += 1
            for dx, dy, cost in self._DIRS:
                nb = (cur[0] + dx, cur[1] + dy)
                if self._blocked(nb):
                    continue
                if dx != 0 and dy != 0:
                    # prevent cutting corners through two blocked tiles
                    if self._blocked((cur[0] + dx, cur[1])) or \
                       self._blocked((cur[0], cur[1] + dy)):
                        continue
                ng = g_score[cur] + cost
                if ng < g_score.get(nb, float("inf")) - 1e-9:
                    g_score[nb] = ng
                    came[nb] = cur
                    heapq.heappush(
                        open_heap,
                        (ng + _octile(nb, goal), ng, nb))
                closed.add(nb)
        # no route found -> straight-line fallback is chosen by the caller
        self._store(cache_key, None)
        return None

    def _store(self, key, path) -> None:
        if self._path_cache_size >= 200:
            self._path_cache.clear()
            self._path_cache_size = 0
        if path:
            self._path_cache[key] = path
            self._path_cache_size += 1

    # ------------------------------------------------------------------
    def plan(self, z) -> None:
        """Recompute a zombie's path toward the player's current tile."""
        zt = (int(round(z.x)), int(round(z.y)))
        if self._blocked(zt):
            zt = tuple(self.grid.find_clear_tile(zt))
        pz = (int(round(z._tx)), int(round(z._ty)))
        path = self.a_star(zt, pz)
        z.path = path
        z.path_i = 0
        z.repath_timer = z._repath_cd

    def velocity(self, z, target_x: float, target_y: float) -> Tuple[float, float]:
        """World-space direction (unscaled) the zombie should move toward."""
        dx = target_x - z.x
        dy = target_y - z.y
        m = math.hypot(dx, dy)
        if z.path and z.path_i < len(z.path):
            nx, ny = z.path[z.path_i]
            cx, cy = nx + 0.5, ny + 0.5
            px, py = cx - z.x, cy - z.y
            pm = math.hypot(px, py)
            if pm < 0.4:
                z.path_i += 1
                if z.path_i >= len(z.path):
                    z.path = None
                    return dx / m, dy / m
                nx, ny = z.path[z.path_i]
                cx, cy = nx + 0.5, ny + 0.5
                px, py = cx - z.x, cy - z.y
                pm = math.hypot(px, py) or 1.0
            return px / pm, py / pm
        # fallback: straight toward target (used when no path / no route)
        return dx / m, dy / m
