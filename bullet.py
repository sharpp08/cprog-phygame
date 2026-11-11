# bullet.py - Projectile class for shooting zombies

import pygame
import math
from settings import *

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, angle, damage=BULLET_DAMAGE, speed=BULLET_SPEED):
        """
        angle: a world-space direction, given either as:
          - a scalar radians angle (legacy: velocity = (cos, sin) * speed), or
          - a (vx, vy) world-space unit velocity vector (new: used by the
            isometric aim so the on-screen flight direction matches the mouse).
        """
        super().__init__()
        self.damage = damage
        self.speed = speed

        if isinstance(angle, (tuple, list)):
            aim_vx, aim_vy = angle
            mag = math.hypot(aim_vx, aim_vy)
            if mag < 1e-6:
                aim_vx, aim_vy, mag = 1.0, 0.0, 1.0
            self.angle = math.atan2(aim_vy, aim_vx)
            self.vx = (aim_vx / mag) * speed
            self.vy = (aim_vy / mag) * speed
        else:
            self.angle = angle
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed

        self.image = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(self.image, BULLET_COLOR, (4, 4), 3)
        pygame.draw.circle(self.image, (255, 255, 200), (4, 4), 1)
        self.rect = self.image.get_rect(center=(x, y))

        self.x = float(x)
        self.y = float(y)
        self.z = 14.0
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
