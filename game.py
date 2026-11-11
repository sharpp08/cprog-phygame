# game.py - Core game loop and state management (isometric 2.5D)

import pygame
import math
import random
import json
import os
from settings import *
from player import Player
from zombie import Zombie
from bullet import Bullet
from particle import Particle
from obstacle import Obstacle
from ui import UI, Button
from sound_manager import SoundManager
from iso_camera import IsoCamera
from asset_generator import create_iso_ground_data, create_shadow_surface, create_tile_texture


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.ui = UI(screen)
        self.sound = SoundManager()

        self.state = "menu"  # menu, playing, paused, game_over, controls
        self.score = 0
        self.high_score = self.load_high_score()
        self.wave = 1

        # Isometric camera
        self.camera = IsoCamera()

        # Sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.zombies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()
        self.obstacles = pygame.sprite.Group()

        # Wave tracking
        self.wave_zombies_total = 0
        self.wave_zombies_spawned = 0
        self.zombies_remaining = 0
        self.wave_in_progress = False
        self.wave_break_timer = 0
        self.announcement = ""
        self.announcement_timer = 0
        self.last_spawn_time = 0

        # Screen flash on hit
        self.damage_flash_time = 0

        # Isometric ground data (pre-computed tile polygons in projected space)
        self.ground_tiles = create_iso_ground_data(MAP_WIDTH, MAP_HEIGHT, ISO_TILE_WORLD)

        # Cached shadow surfaces (reused every frame, no per-frame allocation)
        self._shadow_cache = {}

        # Cached vignette overlay (screen-space atmospheric depth)
        self._vignette = self._create_vignette()

        # Ambient particle timers
        self._ambient_timer = 0

        # Buttons for menus
        self.init_buttons()
        self.reset_game()

    # ---- Shadow caching ------------------------------------------------

    def _get_shadow(self, w, h, alpha=80):
        key = (w, h, alpha)
        surf = self._shadow_cache.get(key)
        if surf is None:
            surf = create_shadow_surface(w, h, alpha)
            self._shadow_cache[key] = surf
        return surf

    def _create_vignette(self):
        """Pre-render a subtle radial vignette overlay for atmospheric depth.

        A dark gradient that is transparent at the center and gradually
        darkens toward the screen edges. This simulates a subtle depth
        / atmospheric effect without per-frame cost.
        """
        w, h = SCREEN_WIDTH, SCREEN_HEIGHT
        cx, cy = w // 2, h // 2
        max_dist = math.hypot(cx, cy)
        vignette = pygame.Surface((w, h), pygame.SRCALPHA)

        # Build the vignette in coarse bands for speed (created once at init)
        num_bands = 12
        for i in range(num_bands):
            t = i / num_bands  # 0 = edge (dark), 1 = center (clear)
            # Alpha ramps from ~40 at the outer edge to 0 at 60% in
            alpha = int(40 * (t * t))  # quadratic falloff
            # Draw concentric rounded rectangles from outside in
            shrink = int((1.0 - t) * min(cx, cy) * 0.6)
            if shrink < 0:
                shrink = 0
            rect = pygame.Rect(cx - cx + shrink, cy - cy + shrink,
                               w - shrink * 2, h - shrink * 2)
            if rect.width > 0 and rect.height > 0:
                pygame.draw.rect(vignette, (10, 14, 12, alpha), rect,
                                 width=30, border_radius=40)

        return vignette

    def _draw_vignette(self):
        """Blit the cached vignette overlay on top of the game world."""
        if self._vignette is not None:
            self.screen.blit(self._vignette, (0, 0))

    # ---- Legacy compatibility (tests call create_map_background) --------

    def create_map_background(self):
        # Kept for test compatibility; isometric version uses ground_tiles.
        self.background = pygame.Surface((MAP_WIDTH, MAP_HEIGHT))
        grass_tile = create_tile_texture("grass")
        dirt_tile = create_tile_texture("dirt")
        for x in range(0, MAP_WIDTH, 64):
            for y in range(0, MAP_HEIGHT, 64):
                self.background.blit(grass_tile, (x, y))
        for x in range(200, MAP_WIDTH - 200, 64):
            self.background.blit(dirt_tile, (x, MAP_HEIGHT // 2 - 32))
            self.background.blit(dirt_tile, (x, MAP_HEIGHT // 2 + 32))
        for y in range(200, MAP_HEIGHT - 200, 64):
            self.background.blit(dirt_tile, (MAP_WIDTH // 2 - 32, y))
            self.background.blit(dirt_tile, (MAP_WIDTH // 2 + 32, y))

    def init_buttons(self):
        cx = SCREEN_WIDTH // 2
        btn_w, btn_h = 240, 50
        self.btn_start = Button(cx - btn_w // 2, 280, btn_w, btn_h, "START GAME", self.ui.header_font)
        self.btn_controls = Button(cx - btn_w // 2, 350, btn_w, btn_h, "CONTROLS", self.ui.header_font)
        self.btn_quit = Button(cx - btn_w // 2, 420, btn_w, btn_h, "QUIT", self.ui.header_font)
        self.btn_back = Button(cx - btn_w // 2, 540, btn_w, btn_h, "BACK", self.ui.header_font)

        self.btn_resume = Button(cx - btn_w // 2, 260, btn_w, btn_h, "RESUME", self.ui.header_font)
        self.btn_pause_restart = Button(cx - btn_w // 2, 330, btn_w, btn_h, "RESTART", self.ui.header_font)
        self.btn_pause_menu = Button(cx - btn_w // 2, 400, btn_w, btn_h, "MAIN MENU", self.ui.header_font)

        self.btn_over_restart = Button(cx - btn_w // 2, 360, btn_w, btn_h, "PLAY AGAIN", self.ui.header_font)
        self.btn_over_menu = Button(cx - btn_w // 2, 430, btn_w, btn_h, "MAIN MENU", self.ui.header_font)
        self.btn_over_quit = Button(cx - btn_w // 2, 500, btn_w, btn_h, "QUIT", self.ui.header_font)

    def load_high_score(self):
        filepath = os.path.join(os.path.dirname(__file__), "data", "highscore.json")
        try:
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    data = json.load(f)
                    return data.get("high_score", 0)
        except Exception:
            pass
        return 0

    def save_high_score(self):
        folder = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, "highscore.json")
        try:
            with open(filepath, "w") as f:
                json.dump({"high_score": self.high_score}, f)
        except Exception:
            pass

    def reset_game(self):
        self.score = 0
        self.wave = 1

        self.all_sprites.empty()
        self.zombies.empty()
        self.bullets.empty()
        self.particles.empty()
        self.obstacles.empty()

        self.player = Player(MAP_WIDTH // 2, MAP_HEIGHT // 2)
        self.all_sprites.add(self.player)

        self.spawn_obstacles()
        self.start_wave(1)

    def spawn_obstacles(self):
        types = ["rock", "crate", "tree"]
        for _ in range(35):
            ox = random.randint(100, MAP_WIDTH - 100)
            oy = random.randint(100, MAP_HEIGHT - 100)
            if math.hypot(ox - MAP_WIDTH // 2, oy - MAP_HEIGHT // 2) > 200:
                obs = Obstacle(ox, oy, random.choice(types))
                self.obstacles.add(obs)
                self.all_sprites.add(obs)

    def start_wave(self, wave_num):
        self.wave = wave_num
        self.wave_zombies_total = 5 + (wave_num * 3)
        self.wave_zombies_spawned = 0
        self.zombies_remaining = self.wave_zombies_total
        self.wave_in_progress = True
        self.announcement = f"--- WAVE {self.wave} START ---"
        self.announcement_timer = pygame.time.get_ticks()
        self.last_spawn_time = -1000

    def spawn_zombie(self):
        if self.wave_zombies_spawned >= self.wave_zombies_total:
            return

        z_type = "regular"
        roll = random.random()
        if self.wave >= 4 and roll < 0.2:
            z_type = "tank"
        elif self.wave >= 2 and roll < 0.4:
            z_type = "fast"

        side = random.choice(["top", "bottom", "left", "right"])
        if side == "top":
            x = random.randint(50, MAP_WIDTH - 50)
            y = 50
        elif side == "bottom":
            x = random.randint(50, MAP_WIDTH - 50)
            y = MAP_HEIGHT - 50
        elif side == "left":
            x = 50
            y = random.randint(50, MAP_HEIGHT - 50)
        else:
            x = MAP_WIDTH - 50
            y = random.randint(50, MAP_HEIGHT - 50)

        zombie = Zombie(x, y, z_type)
        self.zombies.add(zombie)
        self.all_sprites.add(zombie)
        self.wave_zombies_spawned += 1

    def handle_shooting(self):
        mouse_pressed = pygame.mouse.get_pressed()
        current_time = pygame.time.get_ticks()

        if mouse_pressed[0]:
            if current_time - self.player.last_shot_time >= GUN_COOLDOWN:
                self.player.last_shot_time = current_time

                tip_dist = 22
                bx = self.player.x + math.cos(self.player.angle) * tip_dist
                by = self.player.y + math.sin(self.player.angle) * tip_dist

                bullet = Bullet(bx, by, self.player.angle)
                self.bullets.add(bullet)
                self.all_sprites.add(bullet)

                flash = Particle(bx, by, YELLOW, size=3, lifetime=4, z=16)
                self.particles.add(flash)
                self.all_sprites.add(flash)

                self.sound.play_shoot()

    def update(self):
        current_time = pygame.time.get_ticks()

        if self.announcement and current_time - self.announcement_timer > 2500:
            self.announcement = ""

        if self.wave_in_progress:
            if self.wave_zombies_spawned < self.wave_zombies_total:
                if current_time - self.last_spawn_time > 800:
                    self.last_spawn_time = current_time
                    self.spawn_zombie()
            elif len(self.zombies) == 0:
                self.wave_in_progress = False
                self.wave_break_timer = current_time
                self.announcement = f"WAVE {self.wave} CLEARED!"
                self.announcement_timer = current_time
        else:
            if current_time - self.wave_break_timer > 3000:
                self.start_wave(self.wave + 1)

        # Player input & update
        keys = pygame.key.get_pressed()
        self.player.handle_input(keys, self.obstacles)
        self.player.update_aim(self.camera)
        self.player.update()

        # Shooting
        self.handle_shooting()

        # Update bullets
        self.bullets.update()

        # Bullet - Obstacle collision
        for bullet in self.bullets:
            for obs in self.obstacles:
                if bullet.rect.colliderect(obs.rect):
                    for _ in range(3):
                        p = Particle(bullet.x, bullet.y, (180, 180, 180), size=2, lifetime=8, z=14)
                        self.particles.add(p)
                        self.all_sprites.add(p)
                    bullet.kill()
                    break

        # Bullet - Zombie collision
        for bullet in self.bullets:
            hits = pygame.sprite.spritecollide(bullet, self.zombies, False)
            if hits:
                bullet.kill()
                for z in hits:
                    died = z.take_damage(bullet.damage)
                    for _ in range(5):
                        p = Particle(bullet.x, bullet.y, DARK_RED, size=3, lifetime=15, z=14)
                        self.particles.add(p)
                        self.all_sprites.add(p)
                    if died:
                        self.score += z.score_value
                        self.sound.play_zombie_death()
                        for _ in range(10):
                            p = Particle(z.x, z.y, RED, size=4, lifetime=25, z=10)
                            self.particles.add(p)
                            self.all_sprites.add(p)
                    else:
                        self.sound.play_hit()
                break

        # Update zombies
        for z in self.zombies:
            z.update(self.player, self.zombies, self.obstacles)

            if z.rect.colliderect(self.player.rect):
                if self.player.take_damage(z.damage):
                    self.damage_flash_time = current_time
                    self.sound.play_hit()
                    if self.player.health <= 0:
                        self.game_over()
                        return

        # Update particles
        self.particles.update()

        # Ambient particles (floating dust motes)
        self._ambient_timer += 1
        if self._ambient_timer >= 30:
            self._ambient_timer = 0
            if len(self.particles) < 60:
                ax = self.camera.x + random.uniform(-400, 400)
                ay = self.camera.y + random.uniform(-300, 300)
                ax = max(20, min(MAP_WIDTH - 20, ax))
                ay = max(20, min(MAP_HEIGHT - 20, ay))
                p = Particle(ax, ay, (160, 170, 140), velocity=(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3)),
                             size=1, lifetime=120, z=random.uniform(8, 20))
                self.particles.add(p)
                self.all_sprites.add(p)

        # Update camera (smooth follow + clamp)
        self.camera.update(self.player.x, self.player.y)

        # Update zombies remaining counter
        self.zombies_remaining = (self.wave_zombies_total - self.wave_zombies_spawned) + len(self.zombies)

    def game_over(self):
        self.state = "game_over"
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()

    # ---- Isometric rendering -------------------------------------------

    def _billboard_pos(self, sprite):
        """Return screen-space blit position for a billboard sprite.

        Anchors the sprite's feet to its projected world position, applying
        any z-height offset (bob/jump/elevation).
        """
        z = getattr(sprite, 'z', 0.0) + getattr(sprite, 'bob_z', 0.0)
        sx, sy = self.camera.world_to_screen(sprite.x, sprite.y, z)
        img = sprite.image
        # Anchor at bottom-center (feet)
        return img, (int(sx - img.get_width() / 2), int(sy - img.get_height()))

    def _draw_shadows(self, sprites):
        """Draw ground-contact shadows for all shadow-casting sprites."""
        for s in sprites:
            sw = getattr(s, 'shadow_w', 0)
            sh = getattr(s, 'shadow_h', 0)
            if sw <= 0 or sh <= 0:
                continue
            sx, sy = self.camera.world_to_screen(s.x, s.y, 0)
            shadow = self._get_shadow(sw, sh, 70)
            self.screen.blit(shadow, (int(sx - sw / 2), int(sy - sh / 2)))

    def _draw_ground(self):
        """Draw visible isometric ground tiles only (culling)."""
        vis = self.camera.visible_world_rect(padding=200)
        offx = self.camera.offx
        offy = self.camera.offy
        screen = self.screen

        for base, accent, pts, center in self.ground_tiles:
            # Cull tiles whose world center is far outside visible rect
            cwx = (center[0] / ISO_SCALE_X + center[1] / ISO_SCALE_Y) / 2.0
            cwy = (center[1] / ISO_SCALE_Y - center[0] / ISO_SCALE_X) / 2.0
            if cwx < vis.left or cwx > vis.right or cwy < vis.top or cwy > vis.bottom:
                continue

            local = [(p[0] - offx, p[1] - offy) for p in pts]
            pygame.draw.polygon(screen, base, local)
            # Subtle accent speckle at tile center for surface variation
            ccx = int((center[0] - offx))
            ccy = int((center[1] - offy))
            pygame.draw.circle(screen, accent, (ccx, ccy), 2)

    def draw(self):
        if self.state == "menu":
            self.draw_start_menu()
        elif self.state == "controls":
            self.draw_controls_menu()
        elif self.state in ["playing", "paused", "game_over"]:
            self._draw_game_world()

            # Screen flash on taking damage
            current_time = pygame.time.get_ticks()
            if current_time - self.damage_flash_time < 120:
                flash_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                flash_surf.fill((255, 0, 0, 70))
                self.screen.blit(flash_surf, (0, 0))

            # HUD (screen-space, unaffected by camera)
            self.ui.draw_hud(
                self.score,
                self.wave,
                self.player.health,
                self.player.max_health,
                self.zombies_remaining,
                self.announcement
            )

            if self.state == "paused":
                self.ui.draw_pause_menu([self.btn_resume, self.btn_pause_restart, self.btn_pause_menu])
            elif self.state == "game_over":
                self.ui.draw_game_over(
                    self.score,
                    self.high_score,
                    self.wave,
                    [self.btn_over_restart, self.btn_over_menu, self.btn_over_quit]
                )

    def _draw_game_world(self):
        # Fill void/background
        self.screen.fill(ISO_VOID)

        # Draw isometric ground tiles (culled to visible region)
        self._draw_ground()

        # Depth-sort all sprites by world depth (x + y). Larger = drawn later
        # = appears in front. This gives correct occlusion for the iso view.
        renderables = []
        for s in self.all_sprites:
            if not s.alive():
                continue
            depth = self.camera.depth(s.x, s.y)
            # Particles and bullets render slightly above to stay visible
            if isinstance(s, Particle):
                depth += 0.5
            renderables.append((depth, s))
        renderables.sort(key=lambda t: t[0])

        sorted_sprites = [s for _, s in renderables]

        # Draw shadows first (all at ground level)
        self._draw_shadows(sorted_sprites)

        # Draw sprites as billboards in depth order
        for s in sorted_sprites:
            img, pos = self._billboard_pos(s)

            # Hit flash tint
            if getattr(s, 'is_hit_flash', False):
                tint = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                tint.fill((255, 100, 100, 100))
                self.screen.blit(img, pos)
                self.screen.blit(tint, pos, special_flags=pygame.BLEND_RGBA_ADD)
            else:
                self.screen.blit(img, pos)

        # Atmospheric depth overlay (cached, cheap screen-space blit)
        self._draw_vignette()

    def draw_start_menu(self):
        self.screen.fill((20, 25, 30))

        title_surf = self.ui.title_font.render(TITLE, True, RED)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 140))
        self.screen.blit(title_surf, title_rect)

        sub_surf = self.ui.font.render("An Isometric 2.5D Survival Experience", True, (180, 180, 180))
        sub_rect = sub_surf.get_rect(center=(SCREEN_WIDTH // 2, 200))
        self.screen.blit(sub_surf, sub_rect)

        high_surf = self.ui.font.render(f"High Score: {self.high_score}", True, YELLOW)
        high_rect = high_surf.get_rect(center=(SCREEN_WIDTH // 2, 235))
        self.screen.blit(high_surf, high_rect)

        self.btn_start.draw(self.screen)
        self.btn_controls.draw(self.screen)
        self.btn_quit.draw(self.screen)

    def draw_controls_menu(self):
        self.screen.fill((25, 30, 35))

        title_surf = self.ui.title_font.render("CONTROLS", True, WHITE)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 100))
        self.screen.blit(title_surf, title_rect)

        controls_list = [
            ("W / Up Arrow", "Move Up"),
            ("A / Left Arrow", "Move Left"),
            ("S / Down Arrow", "Move Down"),
            ("D / Right Arrow", "Move Right"),
            ("Mouse Move", "Aim Weapon"),
            ("Left Mouse Button", "Shoot / Fire Weapon"),
            ("ESC", "Pause / Resume Game"),
            ("R", "Quick Restart (when Game Over)"),
            ("Q / Window Close", "Quit Application")
        ]

        start_y = 170
        for key_text, action_text in controls_list:
            k_surf = self.ui.header_font.render(key_text, True, YELLOW)
            a_surf = self.ui.font.render(action_text, True, WHITE)
            self.screen.blit(k_surf, (SCREEN_WIDTH // 2 - 250, start_y))
            self.screen.blit(a_surf, (SCREEN_WIDTH // 2 + 50, start_y + 8))
            start_y += 38

        self.btn_back.draw(self.screen)

    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()

        if self.state == "menu":
            self.btn_start.check_hover(mouse_pos)
            self.btn_controls.check_hover(mouse_pos)
            self.btn_quit.check_hover(mouse_pos)
        elif self.state == "controls":
            self.btn_back.check_hover(mouse_pos)
        elif self.state == "paused":
            self.btn_resume.check_hover(mouse_pos)
            self.btn_pause_restart.check_hover(mouse_pos)
            self.btn_pause_menu.check_hover(mouse_pos)
        elif self.state == "game_over":
            self.btn_over_restart.check_hover(mouse_pos)
            self.btn_over_menu.check_hover(mouse_pos)
            self.btn_over_quit.check_hover(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q and self.state in ["menu", "controls", "game_over"]:
                    return False
                if event.key == pygame.K_ESCAPE:
                    if self.state == "playing":
                        self.state = "paused"
                    elif self.state == "paused":
                        self.state = "playing"
                    elif self.state == "controls":
                        self.state = "menu"
                if event.key == pygame.K_r and self.state == "game_over":
                    self.reset_game()
                    self.state = "playing"
                if event.key == pygame.K_RETURN and self.state == "menu":
                    self.reset_game()
                    self.state = "playing"

            if self.state == "menu":
                if self.btn_start.is_clicked(event):
                    self.reset_game()
                    self.state = "playing"
                elif self.btn_controls.is_clicked(event):
                    self.state = "controls"
                elif self.btn_quit.is_clicked(event):
                    return False
            elif self.state == "controls":
                if self.btn_back.is_clicked(event):
                    self.state = "menu"
            elif self.state == "paused":
                if self.btn_resume.is_clicked(event):
                    self.state = "playing"
                elif self.btn_pause_restart.is_clicked(event):
                    self.reset_game()
                    self.state = "playing"
                elif self.btn_pause_menu.is_clicked(event):
                    self.state = "menu"
            elif self.state == "game_over":
                if self.btn_over_restart.is_clicked(event):
                    self.reset_game()
                    self.state = "playing"
                elif self.btn_over_menu.is_clicked(event):
                    self.state = "menu"
                elif self.btn_over_quit.is_clicked(event):
                    return False

        return True
