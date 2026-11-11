# player.py - Player character class (isometric billboard rendering)

import pygame
import math
from settings import *
from asset_generator import create_player_sprite

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.original_image = create_player_sprite()
        self.image_right = self.original_image
        self.image_left = pygame.transform.flip(self.original_image, True, False)
        self.image = self.original_image

        self.rect = pygame.Rect(0, 0, 24, 24)
        self.rect.center = (x, y)
        self.x = float(x)
        self.y = float(y)

        self.speed = PLAYER_SPEED
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH

        self.angle = 0.0
        self.facing = 1
        # World-space aim velocity direction (set each frame by update_aim).
        # Used at bullet spawn so the projectile's on-screen flight direction
        # matches the mouse cursor's on-screen direction.
        self.aim_world_vx = 1.0
        self.aim_world_vy = 0.0
        self.last_shot_time = -GUN_COOLDOWN
        self.last_hit_time = -PLAYER_HIT_COOLDOWN
        self.is_hit_flash = False

        self.moving = False
        self.walk_phase = 0.0
        self.bob_z = 0.0
        self.z = 0.0
        self.shadow_w = 28
        self.shadow_h = 10

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

        self.moving = (dx != 0 or dy != 0)

        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071

        self.x += dx * self.speed
        self.rect.centerx = int(self.x)
        self.check_obstacle_collisions(obstacles, 'x', dx)

        self.y += dy * self.speed
        self.rect.centery = int(self.y)
        self.check_obstacle_collisions(obstacles, 'y', dy)

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

    def update_aim(self, camera):
        mouse_pos = pygame.mouse.get_pos()

        # Convert the mouse to a WORLD-space aim target, then compute the
        # aim ANGLE in world space. This is what bullet direction must use so
        # that the bullet's on-screen flight matches the mouse's on-screen
        # direction (see note below).
        world_mouse_x, world_mouse_y = camera.screen_to_world(mouse_pos[0], mouse_pos[1])
        dx = world_mouse_x - self.x
        dy = world_mouse_y - self.y
        self.angle = math.atan2(dy, dx)

        # The bullet is spawned with a world-space velocity of (cos, sin)*speed.
        # Under the iso projection that velocity maps to a SCREEN direction
        # (vx - vy)*SX, (vx + vy)*SY which is NOT the same as the mouse's
        # screen direction. To make bullets visually travel toward the mouse,
        # we store the SCREEN-space direction here and have the spawn site
        # convert it back into a world velocity.
        #
        # Screen vector from player to mouse:
        psx, psy = camera.world_to_screen(self.x, self.y)
        screen_dx = mouse_pos[0] - psx
        screen_dy = mouse_pos[1] - psy
        # Invert the iso projection to get the world-space velocity direction
        # that produces this exact on-screen flight direction:
        #   sx = (wx - wy)*SX ; sy = (wx + wy)*SY
        # For a unit screen direction (ux, uy):
        #   wx_dir = (ux/SX + uy/SY) / 2 ; wy_dir = (uy/SY - ux/SX) / 2
        ux, uy = screen_dx, screen_dy
        len_s = math.hypot(ux, uy)
        if len_s > 0.0001:
            ux /= len_s
            uy /= len_s
        world_vx = (ux / ISO_SCALE_X + uy / ISO_SCALE_Y) / 2.0
        world_vy = (uy / ISO_SCALE_Y - ux / ISO_SCALE_X) / 2.0
        vlen = math.hypot(world_vx, world_vy)
        if vlen > 0.0001:
            world_vx /= vlen
            world_vy /= vlen
        self.aim_world_vx = world_vx
        self.aim_world_vy = world_vy

        if math.cos(self.angle) < 0:
            self.facing = -1
        else:
            self.facing = 1
        self.image = self.image_left if self.facing == -1 else self.image_right

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
        if self.moving:
            self.walk_phase += 0.3
            self.bob_z = abs(math.sin(self.walk_phase)) * 3.0
        else:
            self.walk_phase = 0.0
            self.bob_z = 0.0
