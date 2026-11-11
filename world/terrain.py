"""Terrain queries: tile surface types and grass colour variants."""
from __future__ import annotations

from typing import Sequence

import config


class Terrain:
    def __init__(self, tiles: Sequence[Sequence[int]],
                 grass_var: Sequence[Sequence[int]]) -> None:
        self.tiles = tiles
        self.grass_var = grass_var
        self.w = len(tiles[0]) if tiles else 0
        self.h = len(tiles)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def type(self, x: int, y: int) -> int:
        if not self.in_bounds(x, y):
            return config.T_GRASS
        return self.tiles[y][x]

    def grass_variant(self, x: int, y: int) -> int:
        if not self.in_bounds(x, y):
            return 0
        return self.grass_var[y][x]

    def is_water(self, x: int, y: int) -> bool:
        return self.type(x, y) in (config.T_WATER, config.T_LILY)

    def is_bridge(self, x: int, y: int) -> bool:
        return self.type(x, y) == config.T_BRIDGE

    def is_lily(self, x: int, y: int) -> bool:
        return self.type(x, y) == config.T_LILY
