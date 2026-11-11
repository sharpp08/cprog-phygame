# particle.py - Visual effects particles (blood, sparks, flashes)

import pygame
import random
import math
from settings import *

class Particle(pygame.sprite.Sprite):
    def __init__(self, x, y, color, velocity=None, size=4, lifetime=30, z=0.0):
        super().__init__()
        self.color = color
        self.size = size
        self.lifetime = lifetime
        self.age = 0

        if velocity:
            self.vx, self.vy = velocity
        else:
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1.0, 4.0)
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed

        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.bob_z = 0.0
        self.is_hit_flash = False
        self.shadow_w = 0
        self.shadow_h = 0

        self.image = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (size, size), size)
        self.rect = self.image.get_rect(center=(int(x), int(y)))

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.z += 0.3
        self.rect.center = (int(self.x), int(self.y))

        self.age += 1
        if self.age >= self.lifetime:
            self.kill()
