# obstacle.py - Environmental obstacles (rocks, crates, trees)

import pygame
from asset_generator import create_obstacle_sprite

class Obstacle(pygame.sprite.Sprite):
    def __init__(self, x, y, obs_type="rock"):
        super().__init__()
        self.obs_type = obs_type
        self.image = create_obstacle_sprite(obs_type)
        self.rect = self.image.get_rect(center=(x, y))
