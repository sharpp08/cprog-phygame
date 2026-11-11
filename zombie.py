# zombie.py - Enemy Zombie class (isometric billboard rendering)

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
            coll_w = 18
            self.shadow_w = 20
            self.shadow_h = 8
        elif zombie_type == "tank":
            self.speed = TANK_ZOMBIE_SPEED
            self.health = TANK_ZOMBIE_HEALTH
            self.max_health = TANK_ZOMBIE_HEALTH
            self.damage = TANK_ZOMBIE_DAMAGE
            self.color_skin = (80, 100, 80)
            self.score_value = 30
            coll_w = 36
            self.shadow_w = 40
            self.shadow_h = 14
        else:
            self.speed = REGULAR_ZOMBIE_SPEED
            self.health = REGULAR_ZOMBIE_HEALTH
            self.max_health = REGULAR_ZOMBIE_HEALTH
            self.damage = REGULAR_ZOMBIE_DAMAGE
            self.color_skin = ZOMBIE_SKIN
            self.score_value = 10
            coll_w = 24
            self.shadow_w = 26
            self.shadow_h = 10

        self.original_image = create_zombie_sprite(self.color_skin)
        if zombie_type == "tank":
            self.original_image = pygame.transform.scale(self.original_image, (48, 68))
        elif zombie_type == "fast":
            self.original_image = pygame.transform.scale(self.original_image, (24, 34))

        self.image_right = self.original_image
        self.image_left = pygame.transform.flip(self.original_image, True, False)
        self.image = self.original_image

        self.rect = pygame.Rect(0, 0, coll_w, coll_w)
        self.rect.center = (x, y)
        self.x = float(x)
        self.y = float(y)
        self.last_attack_time = 0

        self.facing = 1
        self.walk_phase = random.uniform(0, math.pi * 2)
        self.bob_z = 0.0
        self.z = 0.0
        self.is_hit_flash = False
        self.hit_flash_time = 0

    def update(self, player, zombies, obstacles):
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy)

        if dist > 1.0:
            vx = (dx / dist) * self.speed
            vy = (dy / dist) * self.speed

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
            self.walk_phase += 0.25
            self.bob_z = abs(math.sin(self.walk_phase)) * 2.0
        else:
            self.bob_z = 0.0

        for obs in obstacles:
            if self.rect.colliderect(obs.rect):
                if self.x > obs.rect.centerx:
                    self.x += 1.0
                else:
                    self.x -= 1.0
                if self.y > obs.rect.centery:
                    self.y += 1.0
                else:
                    self.y -= 1.0

        self.rect.center = (int(self.x), int(self.y))

        if dist > 0:
            if dx < 0:
                self.facing = -1
            else:
                self.facing = 1
            self.image = self.image_left if self.facing == -1 else self.image_right

        current_time = pygame.time.get_ticks()
        if self.is_hit_flash and current_time - self.hit_flash_time > 100:
            self.is_hit_flash = False

    def take_damage(self, amount):
        self.health -= amount
        self.is_hit_flash = True
        self.hit_flash_time = pygame.time.get_ticks()
        if self.health <= 0:
            self.kill()
            return True
        return False
