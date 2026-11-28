"""The playable world: terrain, obstacles, water, lights and spawning.

A :class:`World` wraps the data produced by :mod:`world.map_data` and is what
the renderer, systems and UI query every frame.
"""
from __future__ import annotations

import math
import random
from typing import List, Tuple

import config
from engine.collision import GridMap
from world.obstacles import Obstacle
from world.terrain import Terrain


class World:
    def __init__(self, data: dict) -> None:
        self.W = data["W"]
        self.H = data["H"]
        self.tiles = data["tiles"]
        self.blocks = data["blocks"]
        self.grass_var = data["grass_var"]
        self.elevation = data.get("elevation")
        self.terrain = Terrain(data["tiles"], data["grass_var"])
        self.grid = GridMap(data["blocks"], data.get("tree_radii", {}))
        self.obstacles: List[Obstacle] = \
            [Obstacle.from_dict(o) for o in data["obstacles"]]
        for obstacle in self.obstacles:
            obstacle.z += self.height_at(obstacle.x, obstacle.y) * config.TERRAIN_HEIGHT_SCALE
        self.water_tiles = data["water_tiles"]
        self.lily_tiles = data["lily_tiles"]
        self.bridge = data["bridge"]
        self.shrine = data["shrine"]
        self.waterfall = data["waterfall"]
        self.ruin = data["ruin"]
        self.start = data["start"]
        self.spawn_points = data["spawn_points"]
        self.lights = data["lights"]
        self.loot = data["loot"]
        self._time = 0.0
        # group obstacles by kind for cheap rendering
        self._by_kind: dict = {}
        self._obstacle_chunks: dict = {}
        self._chunk_size = 12
        for o in self.obstacles:
            self._by_kind.setdefault(o.kind, []).append(o)
            key = (int(o.x) // self._chunk_size, int(o.y) // self._chunk_size)
            self._obstacle_chunks.setdefault(key, []).append(o)

    def height_at(self, x: float, y: float) -> float:
        """Bilinearly sample the smooth low-relief terrain height field."""
        if self.elevation is None:
            return 0.0
        x = max(0.0, min(self.W - 1.001, float(x)))
        y = max(0.0, min(self.H - 1.001, float(y)))
        x0, y0 = int(x), int(y)
        x1, y1 = min(self.W - 1, x0 + 1), min(self.H - 1, y0 + 1)
        fx, fy = x - x0, y - y0
        a = self.elevation[y0][x0] * (1.0 - fx) + self.elevation[y0][x1] * fx
        b = self.elevation[y1][x0] * (1.0 - fx) + self.elevation[y1][x1] * fx
        return a * (1.0 - fy) + b * fy

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self._time += dt

    @property
    def time(self) -> float:
        return self._time

    def cull_obstacles(self, minx, miny, maxx, maxy,
                       pad: float = 1.0) -> List[Obstacle]:
        if not self._obstacle_chunks:
            return []
        size = self._chunk_size
        x0 = max(0, int(math.floor(minx - pad)) // size)
        y0 = max(0, int(math.floor(miny - pad)) // size)
        x1 = min((self.W - 1) // size, int(math.floor(maxx + pad)) // size)
        y1 = min((self.H - 1) // size, int(math.floor(maxy + pad)) // size)
        visible = []
        for cy in range(y0, y1 + 1):
            for cx in range(x0, x1 + 1):
                for obstacle in self._obstacle_chunks.get((cx, cy), ()):
                    if obstacle.in_rect(minx, miny, maxx, maxy, pad):
                        visible.append(obstacle)
        return visible

    def obstacles_of(self, kind: str) -> List[Obstacle]:
        return self._by_kind.get(kind, [])

    # ------------------------------------------------------------------
    def grass_near(self, ring: float, radius: float = 8.0) -> List[Tuple[float, float]]:
        """Grass tiles on a ring around the shrine (for wave spawns)."""
        cx, cy = self.shrine
        out = []
        rng = random
        for _ in range(60):
            a = rng.random() * 3.14159 * 2
            rr = radius
            x = int(cx + math.cos(a) * rr)
            y = int(cy + math.sin(a) * rr)
            if self.grid.in_bounds(x, y) and \
                    self.grid.blocks[y][x] == config.BLOCK_NONE and \
                    self.tiles[y][x] not in (config.T_WATER, config.T_BRIDGE):
                out.append((float(x), float(y)))
        return out[:ring]

    def spawn_wave_around_shrine(self, count: int) -> List[Tuple[float, float, str]]:
        tiles = self.grass_near(max(count, 4))
        if not tiles:
            tiles = [(float(s[0]), float(s[1])) for s in self.spawn_points]
        spots = [tiles[i % len(tiles)] for i in range(count)]
        out = []
        for i, (x, y) in enumerate(spots):
            r = random.random()
            if r < 0.34:
                zt = "regular"
            elif r < 0.54:
                zt = "fast"
            elif r < 0.70:
                zt = "tank"
            elif r < 0.86:
                zt = "crawler"
            else:
                zt = "exploder"
            out.append((x + random.uniform(-0.4, 0.4),
                        y + random.uniform(-0.4, 0.4), zt))
        return out
