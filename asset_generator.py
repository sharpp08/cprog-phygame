# asset_generator.py - Procedural isometric 2.5D asset generation for Pygame

import pygame
import math
import random
from settings import *


def _feet_anchor(image):
    """Return the bottom-center anchor point of a billboard sprite."""
    return (image.get_width() // 2, image.get_height())


def create_player_sprite():
    """Front-facing billboard survivor. Anchor = bottom-center (feet)."""
    w, h = 36, 48
    surface = pygame.Surface((w, h), pygame.SRCALPHA)
    skin = (235, 195, 155)
    jacket = (45, 75, 135)
    jacket_dark = (35, 60, 110)
    pants = (50, 50, 60)
    cap = (70, 45, 25)
    gun = (40, 40, 45)

    cx = w // 2  # 18
    feet = h     # 48
    # Legs
    pygame.draw.rect(surface, pants, (cx - 7, feet - 14, 5, 14), border_radius=2)
    pygame.draw.rect(surface, pants, (cx + 2, feet - 14, 5, 14), border_radius=2)
    pygame.draw.rect(surface, (40, 40, 48), (cx - 7, feet - 4, 5, 4))
    pygame.draw.rect(surface, (40, 40, 48), (cx + 2, feet - 4, 5, 4))
    # Torso
    pygame.draw.rect(surface, jacket, (cx - 8, feet - 26, 16, 14), border_radius=3)
    pygame.draw.rect(surface, jacket_dark, (cx - 8, feet - 26, 16, 4), border_radius=2)
    # Head
    pygame.draw.circle(surface, skin, (cx, feet - 30), 6)
    # Cap
    pygame.draw.rect(surface, cap, (cx - 7, feet - 34, 14, 4), border_radius=2)
    pygame.draw.rect(surface, cap, (cx - 2, feet - 37, 9, 4), border_radius=2)
    # Right arm holding gun (points to the right)
    pygame.draw.rect(surface, jacket, (cx + 6, feet - 24, 5, 8), border_radius=2)
    pygame.draw.circle(surface, skin, (cx + 10, feet - 17), 2)
    # Gun barrel pointing right
    pygame.draw.rect(surface, gun, (cx + 10, feet - 18, 12, 3))
    pygame.draw.rect(surface, (60, 60, 65), (cx + 20, feet - 19, 3, 5))
    return surface


def create_zombie_sprite(skin_color=ZOMBIE_SKIN):
    """Front-facing billboard zombie. Anchor = bottom-center (feet)."""
    w, h = 32, 46
    surface = pygame.Surface((w, h), pygame.SRCALPHA)
    cloth = (80, 40, 40)
    cloth_dark = (60, 30, 30)

    cx = w // 2  # 16
    feet = h    # 46
    # Legs (staggered, zombie stance)
    pygame.draw.rect(surface, cloth_dark, (cx - 7, feet - 14, 5, 14), border_radius=2)
    pygame.draw.rect(surface, cloth_dark, (cx + 2, feet - 13, 5, 13), border_radius=2)
    pygame.draw.rect(surface, (50, 50, 40), (cx - 7, feet - 4, 5, 4))
    pygame.draw.rect(surface, (50, 50, 40), (cx + 2, feet - 3, 5, 3))
    # Torso
    pygame.draw.rect(surface, cloth, (cx - 8, feet - 26, 16, 14), border_radius=3)
    pygame.draw.rect(surface, cloth_dark, (cx - 8, feet - 16, 16, 4))
    # Arms outstretched forward (to the right)
    pygame.draw.rect(surface, skin_color, (cx + 4, feet - 23, 12, 4), border_radius=2)
    pygame.draw.rect(surface, skin_color, (cx + 4, feet - 17, 12, 4), border_radius=2)
    pygame.draw.circle(surface, skin_color, (cx + 15, feet - 21), 2)
    pygame.draw.circle(surface, skin_color, (cx + 15, feet - 15), 2)
    # Head
    pygame.draw.circle(surface, skin_color, (cx, feet - 30), 6)
    # Red glowing eyes
    pygame.draw.circle(surface, (255, 0, 0), (cx + 3, feet - 31), 1)
    pygame.draw.circle(surface, (255, 0, 0), (cx - 2, feet - 31), 1)
    # Mouth
    pygame.draw.rect(surface, (60, 20, 20), (cx - 3, feet - 27, 6, 2))
    return surface


def create_obstacle_sprite(obs_type="rock"):
    """Isometric obstacle with visible height. Anchor = bottom-center."""
    if obs_type == "rock":
        w, h = 52, 40
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        cx = w // 2
        base = h
        # Top face (lit)
        pygame.draw.polygon(surface, (130, 130, 140),
            [(cx, base - 34), (cx + 20, base - 20), (cx, base - 6), (cx - 20, base - 20)])
        # Front-left face (dark)
        pygame.draw.polygon(surface, (90, 90, 100),
            [(cx - 20, base - 20), (cx, base - 6), (cx, base - 2), (cx - 20, base - 14)])
        # Front-right face (mid)
        pygame.draw.polygon(surface, (110, 110, 120),
            [(cx + 20, base - 20), (cx, base - 6), (cx, base - 2), (cx + 20, base - 14)])
        # Highlight on top
        pygame.draw.polygon(surface, (160, 160, 170),
            [(cx, base - 34), (cx + 8, base - 27), (cx, base - 20), (cx - 8, base - 27)])
        return surface

    elif obs_type == "crate":
        w, h = 48, 56
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        cx = w // 2
        base = h
        # Isometric box: top, front-left, front-right faces
        top_w = 34
        # Top face
        pygame.draw.polygon(surface, (140, 95, 50),
            [(cx, base - 50), (cx + top_w // 2, base - 40), (cx, base - 30), (cx - top_w // 2, base - 40)])
        # Front-left face
        pygame.draw.polygon(surface, (100, 65, 35),
            [(cx - top_w // 2, base - 40), (cx, base - 30), (cx, base - 8), (cx - top_w // 2, base - 18)])
        # Front-right face
        pygame.draw.polygon(surface, (120, 80, 40),
            [(cx + top_w // 2, base - 40), (cx, base - 30), (cx, base - 8), (cx + top_w // 2, base - 18)])
        # Plank lines on front faces
        pygame.draw.line(surface, (70, 45, 20), (cx - top_w // 2, base - 32), (cx, base - 22), 1)
        pygame.draw.line(surface, (70, 45, 20), (cx + top_w // 2, base - 32), (cx, base - 22), 1)
        pygame.draw.line(surface, (80, 50, 25), (cx - top_w // 2, base - 24), (cx, base - 14), 1)
        pygame.draw.line(surface, (80, 50, 25), (cx + top_w // 2, base - 24), (cx, base - 14), 1)
        # Top edge outline
        pygame.draw.polygon(surface, (90, 55, 28),
            [(cx, base - 50), (cx + top_w // 2, base - 40), (cx, base - 30), (cx - top_w // 2, base - 40)], 1)
        return surface

    elif obs_type == "tree":
        w, h = 56, 104
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        cx = w // 2
        base = h
        # Trunk
        pygame.draw.rect(surface, (90, 60, 30), (cx - 4, base - 30, 8, 30))
        pygame.draw.rect(surface, (70, 45, 22), (cx + 2, base - 30, 3, 30))
        # Foliage (layered circles for depth)
        pygame.draw.circle(surface, (20, 65, 30), (cx, base - 48), 24)
        pygame.draw.circle(surface, (28, 85, 40), (cx - 8, base - 56), 16)
        pygame.draw.circle(surface, (32, 95, 45), (cx + 9, base - 60), 15)
        pygame.draw.circle(surface, (24, 75, 38), (cx, base - 68), 14)
        # Highlights
        pygame.draw.circle(surface, (45, 115, 55), (cx - 5, base - 60), 7)
        pygame.draw.circle(surface, (45, 115, 55), (cx + 6, base - 52), 6)
        return surface

    # Fallback empty
    return pygame.Surface((48, 48), pygame.SRCALPHA)


def create_tile_texture(tile_type="grass"):
    """Legacy top-down tile texture (kept for compatibility)."""
    surface = pygame.Surface((64, 64))
    if tile_type == "grass":
        surface.fill(DARK_GRASS)
        for _ in range(12):
            x = (hash(str(_)) % 55) + 4
            y = (hash(str(_ * 7)) % 55) + 4
            pygame.draw.rect(surface, GRASS_PATCH, (x, y, 4, 8))
    elif tile_type == "dirt":
        surface.fill(DIRT)
        for _ in range(10):
            x = (hash(str(_ * 13)) % 56) + 4
            y = (hash(str(_ * 19)) % 56) + 4
            pygame.draw.rect(surface, DARK_DIRT, (x, y, 6, 6))
    return surface


def _project_tile_corners(gx, gy, tile):
    """Project the 4 world corners of a grid tile to screen-projected coords."""
    x0, y0 = gx * tile, gy * tile
    x1, y1 = (gx + 1) * tile, (gy + 1) * tile
    return [
        ((x0 - y0) * ISO_SCALE_X, (x0 + y0) * ISO_SCALE_Y),
        ((x1 - y0) * ISO_SCALE_X, (x1 + y0) * ISO_SCALE_Y),
        ((x1 - y1) * ISO_SCALE_X, (x1 + y1) * ISO_SCALE_Y),
        ((x0 - y1) * ISO_SCALE_X, (x0 + y1) * ISO_SCALE_Y),
    ]


def create_iso_ground_data(map_w, map_h, tile=ISO_TILE_WORLD):
    """Pre-compute isometric tile data for per-frame rendering.

    Returns a list of (base_color, accent_color, [4 projected corner points],
    (center_proj_x, center_proj_y)) for every tile in the grid. Points are
    in raw projected space; the renderer offsets them by the camera each frame.
    """
    nx = map_w // tile
    ny = map_h // tile
    mid_x = nx // 2
    mid_y = ny // 2

    grass_a = (34, 110, 47)
    grass_a2 = (30, 100, 42)
    grass_b = (40, 125, 55)
    grass_b2 = (36, 115, 50)
    dirt = (90, 70, 50)
    dirt_dark = (78, 60, 42)

    tiles = []
    for gy in range(ny):
        for gx in range(nx):
            if abs(gx - mid_x) <= 0 or abs(gy - mid_y) <= 0:
                base = dirt
                accent = dirt_dark
            elif (gx + gy) % 2 == 0:
                base = grass_a
                accent = grass_a2
            else:
                base = grass_b
                accent = grass_b2

            pts = _project_tile_corners(gx, gy, tile)
            cx_w = (gx + 0.5) * tile
            cy_w = (gy + 0.5) * tile
            center = ((cx_w - cy_w) * ISO_SCALE_X, (cx_w + cy_w) * ISO_SCALE_Y)
            tiles.append((base, accent, pts, center))

    return tiles


def create_shadow_surface(width, height, alpha=90):
    """Create a reusable ground shadow ellipse surface."""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, alpha), (0, 0, width, height))
    return surf
