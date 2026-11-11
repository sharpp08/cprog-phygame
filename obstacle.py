# obstacle.py - Environmental obstacles (rocks, crates, trees)

import pygame
from asset_generator import create_obstacle_sprite

class Obstacle(pygame.sprite.Sprite):
    def __init__(self, x, y, obs_type="rock"):
        super().__init__()
        self.obs_type = obs_type
        self.image = create_obstacle_sprite(obs_type)
        self.x = float(x)
        self.y = float(y)

        if obs_type == "tree":
            self.rect = pygame.Rect(0, 0, 28, 28)
            self.height = 80
            self.shadow_w = 30
            self.shadow_h = 12
        elif obs_type == "crate":
            self.rect = pygame.Rect(0, 0, 36, 36)
            self.height = 48
            self.shadow_w = 34
            self.shadow_h = 14
        else:
            self.rect = pygame.Rect(0, 0, 36, 36)
            self.height = 32
            self.shadow_w = 32
            self.shadow_h = 12

        self.rect.center = (int(x), int(y))
        self.z = 0.0
        self.bob_z = 0.0
        self.is_hit_flash = False
