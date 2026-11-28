"""Seeded, expanded forest map with connected trails and natural clearings."""
from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple

import config


def _ellipse(cx, cy, rx, ry, x, y):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def _height_field(width, height, seed):
    phase = (seed % 997) * 0.013
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            broad = 0.30 * math.sin(x * 0.075 + phase) * math.cos(y * 0.068 - phase * 0.7)
            rolling = 0.17 * math.sin((x + y) * 0.145 + phase * 1.7) + 0.11 * math.cos((x - y) * 0.12 - phase)
            hill_a = 0.62 * math.exp(-(((x - width * 0.22) / 13.0) ** 2 + ((y - height * 0.25) / 17.0) ** 2))
            hill_b = 0.48 * math.exp(-(((x - width * 0.78) / 16.0) ** 2 + ((y - height * 0.72) / 14.0) ** 2))
            basin = -0.38 * math.exp(-(((x - (config.SHRINE_POS[0] + 11)) / 8.0) ** 2 + ((y - (config.SHRINE_POS[1] + 7)) / 6.0) ** 2))
            row.append(max(-0.28, min(1.05, broad + rolling + hill_a + hill_b + basin)))
        rows.append(row)
    return rows


def generate_map(seed: int = 1234) -> Dict:
    rng = random.Random(seed)
    W, H = config.MAP_W, config.MAP_H
    sx, sy = config.SHRINE_POS
    start = (8, H - 9)
    tiles: List[List[int]] = [[config.T_GRASS] * W for _ in range(H)]
    blocks: List[List[int]] = [[config.BLOCK_NONE] * W for _ in range(H)]
    grass_var = [[rng.randrange(5) for _ in range(W)] for _ in range(H)]
    obstacles: List[Dict] = []
    water_tiles: List[Tuple[int, int]] = []
    lily_tiles: List[Tuple[int, int]] = []
    reserved = set()
    path_mask = set()
    tree_radii = {}

    def in_bounds(x, y):
        return 0 <= x < W and 0 <= y < H

    def carve_path(a, b, width=2, phase=0.0):
        x0, y0 = a
        x1, y1 = b
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) * 2))
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        for i in range(steps + 1):
            t = i / steps
            bend = math.sin(t * math.pi) * math.sin(t * math.pi * 2 + phase) * 0.8
            cx = int(round(x0 + dx * t + nx * bend))
            cy = int(round(y0 + dy * t + ny * bend))
            for oy in range(-width, width + 1):
                for ox in range(-width, width + 1):
                    tx, ty = cx + ox, cy + oy
                    if in_bounds(tx, ty) and ox * ox + oy * oy <= (width + 0.75) ** 2:
                        tiles[ty][tx] = config.T_PATH
                        blocks[ty][tx] = config.BLOCK_NONE
                        path_mask.add((tx, ty))

    def clear_area(cx, cy, rx, ry):
        for y in range(max(0, int(cy - ry - 1)), min(H, int(cy + ry + 2))):
            for x in range(max(0, int(cx - rx - 1)), min(W, int(cx + rx + 2))):
                if _ellipse(cx, cy, rx, ry, x, y):
                    tiles[y][x] = config.T_GRASS
                    blocks[y][x] = config.BLOCK_NONE
                    grass_var[y][x] = rng.randrange(5)
                    path_mask.discard((x, y))

    routes = [
        (start, (16, 78), 2), ((16, 78), (25, 68), 2),
        ((25, 68), (36, 59), 2), ((36, 59), (sx, sy), 2),
        ((sx, sy), (56, 36), 1), ((56, 36), (72, 25), 2),
        ((72, 25), (82, 14), 2), ((sx, sy), (66, 55), 2),
        ((66, 55), (78, 69), 2), ((78, 69), (84, 82), 2),
        ((sx, sy), (34, 35), 1), ((34, 35), (20, 24), 2),
        ((20, 24), (12, 14), 2), ((sx, sy), (34, 70), 1),
        ((34, 70), (20, 82), 2),
    ]
    for i, (a, b, width) in enumerate(routes):
        carve_path(a, b, width, seed * 0.013 + i * 0.91)
    clear_area(sx, sy, 9.0, 8.0)
    clear_area(start[0], start[1], 5.0, 4.5)
    clear_area(18, 20, 6.0, 5.0)
    clear_area(78, 17, 6.0, 5.0)
    clear_area(80, 77, 6.0, 5.0)
    clear_area(22, 78, 4.5, 4.0)
    for i, (a, b, width) in enumerate(routes):
        carve_path(a, b, width, seed * 0.013 + i * 0.91)

    pcx, pcy = sx + 11, sy + 7
    prx, pry = 5.8, 4.2
    for y in range(H):
        for x in range(W):
            if _ellipse(pcx, pcy, prx, pry, x, y):
                tiles[y][x] = config.T_WATER
                blocks[y][x] = config.BLOCK_WATER
                water_tiles.append((x, y))
                path_mask.discard((x, y))
            elif (_ellipse(pcx, pcy, prx + 1.5, pry + 1.5, x, y)
                  and not _ellipse(pcx, pcy, prx, pry, x, y)
                  and (y > pcy or x > pcx)):
                tiles[y][x] = config.T_ROCK
                blocks[y][x] = config.BLOCK_SOLID
                reserved.add((x, y))
    for x, y in rng.sample(water_tiles, min(14, len(water_tiles))):
        tiles[y][x] = config.T_LILY
        lily_tiles.append((x, y))
    bridge = []
    for y in range(int(pcy - pry), int(pcy + pry) + 1):
        x = pcx
        if in_bounds(x, y) and tiles[y][x] in (config.T_WATER, config.T_LILY):
            tiles[y][x] = config.T_BRIDGE
            blocks[y][x] = config.BLOCK_NONE
            bridge.append((x, y))

    wx, wy = pcx - 5, pcy + 4
    for yy in range(wy - 1, wy + 2):
        for xx in range(wx - 1, wx + 2):
            if in_bounds(xx, yy):
                blocks[yy][xx] = config.BLOCK_SOLID
                tiles[yy][xx] = config.T_ROCK
                reserved.add((xx, yy))
    obstacles.append(dict(x=sx + 0.5, y=sy + 0.5, kind="shrine", variant=0, z=0.0, solid=True, scale=1.0))
    obstacles.append(dict(x=wx + 0.5, y=wy + 0.5, kind="waterfall", variant=0, z=0.4, solid=True, scale=1.0))

    ruins = [(sx + 17, sy + 15), (18, 20), (78, 17)]
    for rx, ry in ruins:
        if (rx, ry) != (18, 20):
            for dx, dy in ((-1, 0), (0, -1), (1, 0), (0, 1)):
                tx, ty = rx + dx, ry + dy
                if in_bounds(tx, ty):
                    blocks[ty][tx] = config.BLOCK_SOLID
                    tiles[ty][tx] = config.T_DIRT
                    reserved.add((tx, ty))
        obstacles.append(dict(x=rx + 0.5, y=ry + 0.5, kind="ruin", variant=0, z=0.0, solid=True, scale=1.0))
    ruin = ruins[0]

    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if blocks[y][x] != config.BLOCK_NONE or (x, y) in reserved:
                continue
            if tiles[y][x] != config.T_GRASS or (x, y) in path_mask:
                continue
            cluster = (math.sin(x * 0.19 + seed * 0.01) * math.cos(y * 0.17 - seed * 0.013)
                       + math.sin((x + y) * 0.075)) / 3.0
            density = 0.105 + 0.12 * (cluster + 1.0) * 0.5
            if rng.random() >= density:
                continue
            radius = round(rng.uniform(0.27, 0.40), 3)
            blocks[y][x] = config.BLOCK_TREE
            tree_radii[(x, y)] = radius
            reserved.add((x, y))
            obstacles.append(dict(x=x + 0.5, y=y + 0.5, kind="tree", variant=rng.randrange(7),
                                  z=0.0, solid=True, scale=round(rng.uniform(0.78, 1.28), 3),
                                  collision_radius=radius))

    for _ in range(115):
        for _attempt in range(24):
            x, y = rng.randrange(2, W - 2), rng.randrange(2, H - 2)
            if blocks[y][x] == config.BLOCK_NONE and tiles[y][x] == config.T_GRASS and (x, y) not in path_mask and (x, y) not in reserved:
                blocks[y][x] = config.BLOCK_SOLID
                reserved.add((x, y))
                obstacles.append(dict(x=x + 0.5, y=y + 0.5, kind="rock", variant=rng.randrange(2),
                                      z=0.0, solid=True, scale=round(rng.uniform(0.7, 1.25), 3)))
                break

    for _ in range(210):
        for _attempt in range(18):
            x, y = rng.randrange(1, W - 1), rng.randrange(1, H - 1)
            if blocks[y][x] == config.BLOCK_NONE and tiles[y][x] == config.T_GRASS and (x, y) not in path_mask:
                obstacles.append(dict(x=x + 0.5, y=y + 0.5, kind="bush", variant=0,
                                      z=0.0, solid=False, scale=round(rng.uniform(0.72, 1.2), 3)))
                break

    for _ in range(90):
        for _attempt in range(20):
            x, y = rng.randrange(2, W - 2), rng.randrange(2, H - 2)
            if blocks[y][x] == config.BLOCK_NONE and tiles[y][x] == config.T_GRASS and (x, y) not in path_mask and rng.random() < 0.72:
                blocks[y][x] = config.BLOCK_SOLID
                obstacles.append(dict(x=x + 0.5, y=y + 0.5, kind="fallen_log", variant=rng.randrange(3),
                                      z=0.0, solid=True, scale=round(rng.uniform(0.8, 1.3), 3)))
                break
    for _ in range(180):
        x, y = rng.randrange(1, W - 1), rng.randrange(1, H - 1)
        if tiles[y][x] == config.T_GRASS and (x, y) not in path_mask:
            obstacles.append(dict(x=x + 0.5, y=y + 0.5, kind="roots", variant=rng.randrange(3),
                                  z=0.0, solid=False, scale=round(rng.uniform(0.7, 1.25), 3)))

    loot = []
    def put_loot(x, y, ptype):
        if in_bounds(x, y) and blocks[y][x] == config.BLOCK_NONE:
            loot.append((x, y, ptype))
    put_loot(start[0], start[1], "medkit")
    put_loot(start[0] + 1, start[1], "ammo_pistol")
    put_loot(start[0] + 2, start[1] - 1, "battery")
    put_loot(ruin[0], ruin[1] - 1, "weapon_rifle")
    put_loot(ruin[0] + 1, ruin[1], "ammo_rifle")
    put_loot(sx, sy - 3, "ammo_shotgun")
    put_loot(sx - 2, sy, "medkit")
    put_loot(18, 20, "ammo_pistol")
    put_loot(78, 17, "medkit")
    put_loot(82, 78, "weapon_shotgun")
    put_loot(81, 79, "battery")
    for y in range(H - 6, H - 2):
        put_loot(start[0], y, "ammo_pistol")

    spawn_points = [(3, 3), (W // 2, 3), (W - 4, 4), (W - 4, H // 2),
                    (W - 4, H - 4), (W // 2, H - 4), (3, H - 4), (3, H // 2),
                    (18, 20), (78, 17), (80, 77)]
    lights = [(float(sx), float(sy), config.LIGHT_RADIUS_SHRINE, 1.0),
              (float(wx), float(wy), 5.0, 0.7)]
    return {
        "W": W, "H": H, "tiles": tiles, "blocks": blocks, "grass_var": grass_var,
        "elevation": _height_field(W, H, seed), "tree_radii": tree_radii,
        "obstacles": obstacles, "water_tiles": water_tiles, "lily_tiles": lily_tiles,
        "bridge": bridge, "shrine": (sx, sy), "waterfall": (wx, wy), "ruin": ruin,
        "start": start, "spawn_points": spawn_points, "loot": loot, "lights": lights,
    }
