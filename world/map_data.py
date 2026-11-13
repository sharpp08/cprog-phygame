"""Deterministic map generation for the isometric forest-shrine world.

The layout mirrors the reference: a dense autumn forest around a central
clearing, the wooden shrine as a landmark, a lily-pad pond crossed by a stone
bridge, a misty waterfall, scattered rocks/bushes and a ruined outbuilding.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple

import config


def _ellipse(cx, cy, rx, ry, x, y) -> bool:
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def generate_map(seed: int = 1234) -> Dict:
    rng = random.Random(seed)
    W, H = config.MAP_W, config.MAP_H
    sx, sy = config.SHRINE_POS

    tiles: List[List[int]] = [[config.T_GRASS] * W for _ in range(H)]
    blocks: List[List[int]] = [[config.BLOCK_NONE] * W for _ in range(H)]
    grass_var: List[List[int]] = [[rng.randint(0, 4) for _ in range(W)]
                                   for _ in range(H)]

    obstacles: List[Dict] = []
    water_tiles: List[Tuple[int, int]] = []
    lily_tiles: List[Tuple[int, int]] = []
    reserved = set()

    def in_bounds(x, y):
        return 0 <= x < W and 0 <= y < H

    def carve_path(x0, y0, x1, y1, width=2):
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0)))
        for i in range(steps + 1):
            t = i / steps
            px = x0 + (x1 - x0) * t
            py = y0 + (y1 - y0) * t
            for dx in range(-width, width + 1):
                for dy in range(-width, width + 1):
                    tx, ty = int(round(px)) + dx, int(round(py)) + dy
                    if in_bounds(tx, ty):
                        tiles[ty][tx] = config.T_PATH
                        blocks[ty][tx] = config.BLOCK_NONE

    # --- clearing around the shrine ---
    for y in range(H):
        for x in range(W):
            if math.hypot(x - sx, y - sy) <= 6.5:
                tiles[y][x] = config.T_GRASS
                blocks[y][x] = config.BLOCK_NONE
                grass_var[y][x] = rng.randint(0, 4)

    # --- central paths ---
    start = (6, H - 5)
    carve_path(start[0], start[1], sx, sy, 2)
    carve_path(sx, sy, 31, 27, 1)
    carve_path(sx, sy, sx + 12, sy + 12, 1)

    # --- pond (ellipse) ---
    pcx, pcy = 31, 30
    prx, pry = 4.6, 3.2
    for y in range(H):
        for x in range(W):
            if _ellipse(pcx, pcy, prx, pry, x, y):
                tiles[y][x] = config.T_WATER
                blocks[y][x] = config.BLOCK_WATER
                water_tiles.append((x, y))
            elif _ellipse(pcx, pcy, prx + 1.4, pry + 1.4, x, y) and \
                    not _ellipse(pcx, pcy, prx, pry, x, y) and \
                    (y > pcy or x > pcx):
                tiles[y][x] = config.T_ROCK
                blocks[y][x] = config.BLOCK_SOLID
                reserved.add((x, y))

    for t in rng.sample(water_tiles, min(9, len(water_tiles))):
        if tiles[t[1]][t[0]] == config.T_WATER:
            tiles[t[1]][t[0]] = config.T_LILY
            lily_tiles.append(t)

    # --- stone bridge across the pond (north-south) ---
    bridge = []
    for y in range(int(pcy - pry), int(pcy + pry) + 1):
        x = pcx
        if in_bounds(x, y) and tiles[y][x] in (config.T_WATER,
                                                config.T_LILY,
                                                config.T_GRASS):
            tiles[y][x] = config.T_BRIDGE
            blocks[y][x] = config.BLOCK_NONE
            bridge.append((x, y))

    # --- waterfall (rock outcrop at the pond's west rim) ---
    wx, wy = 26, 33
    for yy in range(wy - 1, wy + 2):
        for xx in range(wx - 1, wx + 2):
            if in_bounds(xx, yy):
                blocks[yy][xx] = config.BLOCK_SOLID
                tiles[yy][xx] = config.T_ROCK
                reserved.add((xx, yy))
    obstacles.append(dict(x=sx, y=sy, kind="shrine", variant=0, z=0.0,
                          solid=True))
    obstacles.append(dict(x=wx, y=wy, kind="waterfall", variant=0, z=0.4,
                          solid=True))

    # --- forest: trees ---
    def place_tree():
        for _ in range(80):
            x = rng.randint(1, W - 2)
            y = rng.randint(1, H - 2)
            if (x, y) in reserved or blocks[y][x] != config.BLOCK_NONE:
                continue
            if math.hypot(x - sx, y - sy) <= 4.5:
                continue
            if tiles[y][x] in (config.T_PATH, config.T_WATER,
                               config.T_BRIDGE, config.T_LILY,
                               config.T_ROCK):
                continue
            if math.hypot(x - start[0], y - start[1]) < 3.0:
                continue
            edge = max(abs(x - W / 2) / (W / 2),
                       abs(y - H / 2) / (H / 2))
            if rng.random() > 0.35 + edge * 0.6:
                continue
            blocks[y][x] = config.BLOCK_SOLID
            reserved.add((x, y))
            obstacles.append(dict(x=x, y=y, kind="tree",
                                  variant=rng.randint(0, 6), z=0.0,
                                  solid=True))
            return True
        return False

    for _ in range(150):
        place_tree()

    # --- rocks ---
    for _ in range(24):
        placed = False
        for _t in range(30):
            x = rng.randint(1, W - 2)
            y = rng.randint(1, H - 2)
            if blocks[y][x] == config.BLOCK_NONE and \
                    (x, y) not in reserved and \
                    tiles[y][x] in (config.T_GRASS, config.T_DIRT):
                blocks[y][x] = config.BLOCK_SOLID
                reserved.add((x, y))
                obstacles.append(dict(x=x, y=y, kind="rock",
                                      variant=rng.randint(0, 1), z=0.0,
                                      solid=True))
                placed = True
                break

    # --- bushes (walkable) ---
    for _ in range(26):
        for _t in range(30):
            x = rng.randint(1, W - 2)
            y = rng.randint(1, H - 2)
            if blocks[y][x] == config.BLOCK_NONE and \
                    tiles[y][x] == config.T_GRASS:
                obstacles.append(dict(x=x, y=y, kind="bush",
                                      variant=0, z=0.0, solid=False))
                break

    # --- ruined outbuilding (loot cache) ---
    rx, ry = sx + 12, sy + 12
    for dx, dy in ((-1, 0), (0, -1), (1, 0), (1, -1), (0, 1)):
        tx, ty = rx + dx, ry + dy
        if in_bounds(tx, ty):
            blocks[ty][tx] = config.BLOCK_SOLID
            tiles[ty][tx] = config.T_DIRT
            reserved.add((tx, ty))
    obstacles.append(dict(x=rx, y=ry, kind="ruin", variant=0, z=0.0,
                          solid=True))

    # --- loot placement ---
    loot: List[Tuple[int, int, str]] = []

    def put_loot(x, y, ptype):
        if in_bounds(x, y) and blocks[y][x] == config.BLOCK_NONE:
            loot.append((x, y, ptype))

    put_loot(start[0], start[1], "medkit")
    put_loot(start[0] + 1, start[1], "ammo_pistol")
    put_loot(start[0] + 2, start[1] - 1, "battery")
    put_loot(rx, ry - 1, "weapon_rifle")
    put_loot(rx, ry, "ammo_rifle")
    put_loot(sx, sy - 3, "ammo_shotgun")
    put_loot(sx - 2, sy, "medkit")
    for y in range(H - 6, H - 2):
        put_loot(6, y, "ammo_pistol")
    for x in range(2, 6):
        put_loot(x, 6, "medkit")
    put_loot(40, 4, "weapon_shotgun")
    put_loot(39, 5, "battery")

    spawn_points = [(2, 2), (W - 3, 2), (2, H - 3), (W - 3, H - 3)]
    lights = [(float(sx), float(sy), config.LIGHT_RADIUS_SHRINE, 1.0),
              (float(wx), float(wy), 5.0, 0.7)]

    return {
        "W": W, "H": H,
        "tiles": tiles, "blocks": blocks, "grass_var": grass_var,
        "obstacles": obstacles, "water_tiles": water_tiles,
        "lily_tiles": lily_tiles, "bridge": bridge,
        "shrine": (sx, sy), "waterfall": (wx, wy), "ruin": (rx, ry),
        "start": start, "spawn_points": spawn_points, "loot": loot,
        "lights": lights,
    }

