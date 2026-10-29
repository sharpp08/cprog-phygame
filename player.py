# player.py - Player character class

import pygame
import math
from settings import *
from asset_generator import create_player_sprite

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.original_image = create_player_sprite()
        self.image = self.original_image
        self.rect = self.image.get_rect(center=(x, y))
        self.x = float(x)
        self.y = float(y)
        
        self.speed = PLAYER_SPEED
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        
        self.angle = 0.0
        self.last_shot_time = -GUN_COOLDOWN
        self.last_hit_time = -PLAYER_HIT_COOLDOWN
        self.is_hit_flash = False

    def handle_input(self, keys, obstacles):
        def is_pressed(k):
            try:
                return bool(keys[k])
            except (IndexError, KeyError, TypeError):
                return False

        dx = 0
        dy = 0
        if is_pressed(pygame.K_w) or is_pressed(pygame.K_UP):
            dy -= 1
        if is_pressed(pygame.K_s) or is_pressed(pygame.K_DOWN):
            dy += 1
        if is_pressed(pygame.K_a) or is_pressed(pygame.K_LEFT):
            dx -= 1
        if is_pressed(pygame.K_d) or is_pressed(pygame.K_RIGHT):
            dx += 1
            
        # Normalize diagonal movement
        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071
            
        # Move X with obstacle collision
        self.x += dx * self.speed
        self.rect.centerx = int(self.x)
        self.check_obstacle_collisions(obstacles, 'x', dx)
        
        # Move Y with obstacle collision
        self.y += dy * self.speed
        self.rect.centery = int(self.y)
        self.check_obstacle_collisions(obstacles, 'y', dy)
        
        # Keep inside map bounds
        self.x = max(32, min(MAP_WIDTH - 32, self.x))
        self.y = max(32, min(MAP_HEIGHT - 32, self.y))
        self.rect.center = (int(self.x), int(self.y))

    def check_obstacle_collisions(self, obstacles, axis, delta):
        for obs in obstacles:
            if self.rect.colliderect(obs.rect):
                if axis == 'x':
                    if delta > 0:
                        self.rect.right = obs.rect.left
                    elif delta < 0:
                        self.rect.left = obs.rect.right
                    self.x = float(self.rect.centerx)
                elif axis == 'y':
                    if delta > 0:
                        self.rect.bottom = obs.rect.top
                    elif delta < 0:
                        self.rect.top = obs.rect.bottom
                    self.y = float(self.rect.centery)

    def update_aim(self, camera_x, camera_y):
        mouse_pos = pygame.mouse.get_pos()
        # Convert screen mouse pos to world coordinates
        world_mouse_x = mouse_pos[0] + camera_x
        world_mouse_y = mouse_pos[1] + camera_y
        
        dx = world_mouse_x - self.x
        dy = world_mouse_y - self.y
        self.angle = math.atan2(dy, dx)
        
        # Rotate image towards angle
        degrees = -math.degrees(self.angle)
        self.image = pygame.transform.rotate(self.original_image, degrees)
        self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))

    def take_damage(self, amount):
        current_time = pygame.time.get_ticks()
        if current_time - self.last_hit_time >= PLAYER_HIT_COOLDOWN:
            self.health = max(0, self.health - amount)
            self.last_hit_time = current_time
            self.is_hit_flash = True
            return True
        return False

    def update(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.last_hit_time > 150:
            self.is_hit_flash = False
