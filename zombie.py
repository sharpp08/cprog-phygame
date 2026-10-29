# zombie.py - Enemy Zombie class

import pygame
import math
import random
from settings import *
from asset_generator import create_zombie_sprite

class Zombie(pygame.sprite.Sprite):
    def __init__(self, x, y, zombie_type="regular"):
        super().__init__()
        self.zombie_type = zombie_type
        
        if zombie_type == "fast":
            self.speed = FAST_ZOMBIE_SPEED
            self.health = FAST_ZOMBIE_HEALTH
            self.max_health = FAST_ZOMBIE_HEALTH
            self.damage = FAST_ZOMBIE_DAMAGE
            self.color_skin = FAST_ZOMBIE_SKIN
            self.score_value = 15
        elif zombie_type == "tank":
            self.speed = TANK_ZOMBIE_SPEED
            self.health = TANK_ZOMBIE_HEALTH
            self.max_health = TANK_ZOMBIE_HEALTH
            self.damage = TANK_ZOMBIE_DAMAGE
            self.color_skin = (80, 100, 80)
            self.score_value = 30
        else:  # regular
            self.speed = REGULAR_ZOMBIE_SPEED
            self.health = REGULAR_ZOMBIE_HEALTH
            self.max_health = REGULAR_ZOMBIE_HEALTH
            self.damage = REGULAR_ZOMBIE_DAMAGE
            self.color_skin = ZOMBIE_SKIN
            self.score_value = 10
            
        self.original_image = create_zombie_sprite(self.color_skin)
        if zombie_type == "tank":
            self.original_image = pygame.transform.scale(self.original_image, (44, 44))
        elif zombie_type == "fast":
            self.original_image = pygame.transform.scale(self.original_image, (26, 26))
            
        self.image = self.original_image
        self.rect = self.image.get_rect(center=(x, y))
        self.x = float(x)
        self.y = float(y)
        self.last_attack_time = 0

    def update(self, player, zombies, obstacles):
        # Direction towards player
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy)
        
        if dist > 1.0:
            vx = (dx / dist) * self.speed
            vy = (dy / dist) * self.speed
            
            # Simple separation from other zombies to avoid stacking
            sep_x = 0
            sep_y = 0
            for other in zombies:
                if other != self:
                    ox = self.x - other.x
                    oy = self.y - other.y
                    odist = math.hypot(ox, oy)
                    if 0 < odist < 30:
                        sep_x += (ox / odist) * 1.5
                        sep_y += (oy / odist) * 1.5
                        
            self.x += vx + sep_x
            self.y += vy + sep_y
            
        # Obstacle collision avoidance
        for obs in obstacles:
            if self.rect.colliderect(obs.rect):
                # Simple push back
                if self.x > obs.rect.centerx:
                    self.x += 1.0
                else:
                    self.x -= 1.0
                if self.y > obs.rect.centery:
                    self.y += 1.0
                else:
                    self.y -= 1.0
                    
        self.rect.center = (int(self.x), int(self.y))
        
        # Rotate towards player
        if dist > 0:
            angle = math.atan2(dy, dx)
            degrees = -math.degrees(angle)
            self.image = pygame.transform.rotate(self.original_image, degrees)
            self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.kill()
            return True
        return False
