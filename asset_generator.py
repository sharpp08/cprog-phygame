# asset_generator.py - Procedural pixel-art asset generation for Pygame

import pygame
import math
from settings import *

def create_player_sprite():
    # 32x32 pixel art survivor facing right (+X)
    surface = pygame.Surface((32, 32), pygame.SRCALPHA)
    # Body (jacket/clothes)
    pygame.draw.rect(surface, (45, 75, 135), (8, 9, 14, 14), border_radius=3)
    # Head
    pygame.draw.circle(surface, (235, 195, 155), (15, 16), 5)
    # Survivor cap
    pygame.draw.rect(surface, (70, 45, 25), (11, 13, 7, 6), border_radius=2)
    # Hands holding weapon
    pygame.draw.circle(surface, (235, 195, 155), (18, 13), 2)
    pygame.draw.circle(surface, (235, 195, 155), (18, 19), 2)
    # Gun barrel pointing right
    pygame.draw.rect(surface, (40, 40, 45), (18, 15, 12, 3))
    return surface

def create_zombie_sprite(skin_color=ZOMBIE_SKIN):
    # 32x32 pixel art zombie facing right (+X)
    surface = pygame.Surface((32, 32), pygame.SRCALPHA)
    # Torn clothes / body
    pygame.draw.rect(surface, (80, 40, 40), (6, 8, 14, 16), border_radius=3)
    # Head
    pygame.draw.circle(surface, skin_color, (18, 16), 6)
    # Red glowing eyes
    pygame.draw.circle(surface, (255, 0, 0), (21, 14), 1)
    pygame.draw.circle(surface, (255, 0, 0), (21, 18), 1)
    # Arms outstretched forward toward right (+X)
    pygame.draw.rect(surface, skin_color, (14, 9, 14, 4), border_radius=2)
    pygame.draw.rect(surface, skin_color, (14, 19, 14, 4), border_radius=2)
    return surface

def create_obstacle_sprite(obs_type="rock"):
    surface = pygame.Surface((48, 48), pygame.SRCALPHA)
    if obs_type == "rock":
        pygame.draw.ellipse(surface, (90, 90, 100), (4, 8, 40, 32))
        pygame.draw.ellipse(surface, (120, 120, 130), (10, 12, 28, 20))
        pygame.draw.ellipse(surface, (60, 60, 70), (8, 24, 32, 14))
    elif obs_type == "crate":
        pygame.draw.rect(surface, (110, 75, 40), (4, 4, 40, 40), border_radius=4)
        pygame.draw.rect(surface, (80, 50, 25), (6, 6, 36, 36), border_radius=2)
        pygame.draw.line(surface, (60, 35, 15), (4, 4), (44, 44), 3)
        pygame.draw.line(surface, (60, 35, 15), (4, 44), (44, 4), 3)
    elif obs_type == "tree":
        # Trunk
        pygame.draw.rect(surface, (90, 60, 30), (20, 28, 8, 16))
        # Foliage
        pygame.draw.circle(surface, (25, 80, 35), (24, 20), 18)
        pygame.draw.circle(surface, (35, 100, 45), (18, 16), 12)
        pygame.draw.circle(surface, (30, 90, 40), (30, 18), 12)
    return surface

def create_tile_texture(tile_type="grass"):
    surface = pygame.Surface((64, 64))
    if tile_type == "grass":
        surface.fill(DARK_GRASS)
        # Add subtle noise / blades
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
