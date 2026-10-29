# bullet.py - Projectile class for shooting zombies

import pygame
import math
from settings import *

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, angle, damage=BULLET_DAMAGE, speed=BULLET_SPEED):
        super().__init__()
        self.damage = damage
        self.speed = speed
        self.angle = angle
        
        # Create small bullet surface
        self.image = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(self.image, BULLET_COLOR, (4, 4), 3)
        self.rect = self.image.get_rect(center=(x, y))
        
        # Calculate velocity vectors
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed
        
        self.x = float(x)
        self.y = float(y)
        self.distance_traveled = 0.0
        self.max_range = BULLET_RANGE

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.rect.center = (int(self.x), int(self.y))
        
        dist = math.hypot(self.vx, self.vy)
        self.distance_traveled += dist
        if self.distance_traveled >= self.max_range:
            self.kill()
