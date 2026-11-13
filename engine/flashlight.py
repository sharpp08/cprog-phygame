"""World-aware flashlight ray casting for the isometric tile world.

The renderer consumes a small fan of rays and rasterizes adjacent wedges into
its cached darkness mask. Rays stop at solid obstacles, accumulate distance
and material absorption, and use a height-derived ground normal for diffuse
response. This remains a CPU/Pygame path and does not require a GL context.
"""
from __future__ import annotations

import math
from typing import List, Tuple

import config


_SURFACE_RESPONSE = {
    config.T_GRASS: 0.78, config.T_DIRT: 0.73, config.T_PATH: 0.88,
    config.T_WATER: 1.08, config.T_BRIDGE: 0.91,
    config.T_LILY: 0.98, config.T_ROCK: 0.62,
}
_SURFACE_ABSORPTION = {
    config.T_GRASS: 0.006, config.T_DIRT: 0.010, config.T_PATH: 0.004,
    config.T_WATER: 0.002, config.T_BRIDGE: 0.003,
    config.T_LILY: 0.003, config.T_ROCK: 0.016,
}
# Small height offsets approximate local surface slopes at material boundaries.
_SURFACE_HEIGHT = {
    config.T_GRASS: 0.015, config.T_DIRT: 0.0, config.T_PATH: -0.008,
    config.T_WATER: -0.12, config.T_BRIDGE: 0.025,
    config.T_LILY: -0.09, config.T_ROCK: 0.12,
}


def _tile(world, x: int, y: int) -> int:
    if x < 0 or y < 0 or x >= world.W or y >= world.H:
        return config.T_ROCK
    return world.tiles[y][x]


def _height(world, x: int, y: int) -> float:
    return _SURFACE_HEIGHT.get(_tile(world, x, y), 0.0)


def _normal_response(world, x: float, y: float,
                     ray_dx: float, ray_dy: float) -> float:
    """Lambert-like diffuse term from the local tile-height gradient."""
    tx, ty = int(math.floor(x)), int(math.floor(y))
    gx = (_height(world, tx + 1, ty) - _height(world, tx - 1, ty)) * 0.5
    gy = (_height(world, tx, ty + 1) - _height(world, tx, ty - 1)) * 0.5
    incidence = (0.32 + gx * ray_dx + gy * ray_dy) / (
        0.32 * math.sqrt(1.0 + gx * gx + gy * gy))
    return max(0.55, min(1.12, incidence))


def trace_flashlight_beam(
    world,
    origin: Tuple[float, float],
    aim: Tuple[float, float],
    max_range: float = 19.5,
    ray_count: int = 49,
    half_spread: float = 0.52,
) -> List[Tuple[float, float, float, int]]:
    """Return ordered (end_x, end_y, energy, surface_type) beam rays.

    Solid obstacles terminate rays. Distance attenuation, traversed material
    absorption, surface reflectance, incidence and angular feathering all
    contribute to energy in the range 0..1.
    """
    ox, oy = float(origin[0]), float(origin[1])
    dx, dy = float(aim[0]), float(aim[1])
    aim_len = math.hypot(dx, dy)
    if aim_len <= 1e-8:
        dx, dy, aim_len = 1.0, 0.0, 1.0
    dx, dy = dx / aim_len, dy / aim_len

    blockers = {
        (int(o.x), int(o.y))
        for o in getattr(world, "obstacles", ())
        if bool(getattr(o, "solid", True))
    }
    count = max(3, int(ray_count))
    if count % 2 == 0:
        count += 1
    max_range = max(0.5, float(max_range))
    half_spread = max(0.05, min(1.1, float(half_spread)))
    step = 0.16
    rays: List[Tuple[float, float, float, int]] = []

    for index in range(count):
        t = index / (count - 1)
        angle = (t * 2.0 - 1.0) * half_spread
        ca, sa = math.cos(angle), math.sin(angle)
        rdx = dx * ca - dy * sa
        rdy = dx * sa + dy * ca
        edge = max(0.0, math.cos(
            angle / half_spread * math.pi * 0.5)) ** 1.35

        distance = 0.0
        absorption = 0.0
        last_surface = _tile(world, int(ox), int(oy))
        end_x, end_y = ox, oy
        while distance < max_range:
            next_distance = min(max_range, distance + step)
            px = ox + rdx * next_distance
            py = oy + rdy * next_distance
            tx, ty = int(math.floor(px)), int(math.floor(py))
            if (tx, ty) in blockers:
                distance = max(0.0, next_distance - step * 0.55)
                end_x = ox + rdx * distance
                end_y = oy + rdy * distance
                break
            last_surface = _tile(world, tx, ty)
            absorption += _SURFACE_ABSORPTION.get(last_surface, 0.008) * step
            distance = next_distance
            end_x, end_y = px, py

        material = _SURFACE_RESPONSE.get(last_surface, 0.76)
        normal = _normal_response(world, end_x, end_y, rdx, rdy)
        attenuation = math.exp(-0.018 * distance - absorption)
        inverse_square = 1.0 / (1.0 + 0.025 * distance)
        energy = max(0.0, min(1.0,
            attenuation * inverse_square * material * normal * edge))
        rays.append((end_x, end_y, energy, last_surface))
    return rays
