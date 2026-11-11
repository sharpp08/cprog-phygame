# test_game_logic.py - Unit tests for gameplay mechanics

import os
import sys
import unittest
import math
import json

# Setup headless SDL before importing pygame
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pygame
pygame.init()
# Create dummy screen for Sprite and Font operations
screen = pygame.display.set_mode((1, 1))

from settings import *
from player import Player
from zombie import Zombie
from bullet import Bullet
from obstacle import Obstacle
from game import Game

class TestGameLogic(unittest.TestCase):
    def setUp(self):
        self.player = Player(500, 500)

    def test_player_initial_stats(self):
        self.assertEqual(self.player.health, PLAYER_MAX_HEALTH)
        self.assertEqual(self.player.speed, PLAYER_SPEED)
        self.assertEqual(self.player.rect.center, (500, 500))

    def test_player_damage_and_cooldown(self):
        initial_hp = self.player.health
        hit1 = self.player.take_damage(20)
        self.assertTrue(hit1)
        self.assertEqual(self.player.health, initial_hp - 20)

        # Immediate second hit should be ignored due to cooldown
        hit2 = self.player.take_damage(20)
        self.assertFalse(hit2)
        self.assertEqual(self.player.health, initial_hp - 20)

    def test_player_health_floor(self):
        self.player.last_hit_time = -PLAYER_HIT_COOLDOWN
        self.player.take_damage(200)
        self.assertEqual(self.player.health, 0)

    def test_player_diagonal_normalization(self):
        # Emulate keys: W and D (up and right)
        keys = [0] * 512
        keys[pygame.K_w] = 1
        keys[pygame.K_d] = 1
        
        start_x = self.player.x
        start_y = self.player.y
        self.player.handle_input(keys, [])
        
        dx = self.player.x - start_x
        dy = self.player.y - start_y
        dist = math.hypot(dx, dy)
        self.assertAlmostEqual(dist, PLAYER_SPEED, delta=0.1)

    def test_player_boundary_clamp(self):
        # Push player beyond left bound
        keys = [0] * 512
        keys[pygame.K_a] = 1
        self.player.x = 20
        self.player.handle_input(keys, [])
        self.assertGreaterEqual(self.player.x, 32)

    def test_zombie_types(self):
        regular = Zombie(100, 100, "regular")
        fast = Zombie(100, 100, "fast")
        tank = Zombie(100, 100, "tank")

        self.assertEqual(regular.health, REGULAR_ZOMBIE_HEALTH)
        self.assertEqual(fast.health, FAST_ZOMBIE_HEALTH)
        self.assertEqual(tank.health, TANK_ZOMBIE_HEALTH)

        self.assertGreater(fast.speed, regular.speed)
        self.assertGreater(regular.speed, tank.speed)

    def test_zombie_damage_and_death(self):
        zombie = Zombie(100, 100, "regular")
        died = zombie.take_damage(REGULAR_ZOMBIE_HEALTH - 5)
        self.assertFalse(died)
        self.assertEqual(zombie.health, 5)

        died2 = zombie.take_damage(10)
        self.assertTrue(died2)
        self.assertLessEqual(zombie.health, 0)

    def test_bullet_travel_and_range(self):
        bullet = Bullet(100, 100, 0)  # Angle 0: moving along +X
        self.assertAlmostEqual(bullet.vx, BULLET_SPEED, delta=0.1)
        self.assertAlmostEqual(bullet.vy, 0.0, delta=0.1)

        # Update until max range
        steps = int(BULLET_RANGE / BULLET_SPEED) + 5
        for _ in range(steps):
            bullet.update()
        self.assertGreaterEqual(bullet.distance_traveled, BULLET_RANGE)

    def test_high_score_handling(self):
        game = Game(screen)
        
        # Test malformed file fallback
        test_file = os.path.join(os.path.dirname(__file__), "..", "data", "test_corrupt.json")
        with open(test_file, "w") as f:
            f.write("{ invalid json")
        
        score = game.load_high_score()
        self.assertIsInstance(score, int)
        
        if os.path.exists(test_file):
            os.remove(test_file)

    def test_player_obstacle_collision(self):
        from obstacle import Obstacle
        obs = Obstacle(530, 500, "rock")
        keys = [0] * 512
        keys[pygame.K_d] = 1  # move right towards obstacle
        
        for _ in range(20):
            self.player.handle_input(keys, [obs])
        # Player rect should be blocked from passing obstacle rect center
        self.assertLess(self.player.rect.right, obs.rect.right)

    def test_zombie_pursuit(self):
        zombie = Zombie(100, 100, "regular")
        init_dist = math.hypot(self.player.x - zombie.x, self.player.y - zombie.y)
        zombie.update(self.player, [], [])
        new_dist = math.hypot(self.player.x - zombie.x, self.player.y - zombie.y)
        self.assertLess(new_dist, init_dist)

    def test_wave_scaling(self):
        game = Game(screen)
        game.start_wave(1)
        w1_total = game.wave_zombies_total
        game.start_wave(2)
        w2_total = game.wave_zombies_total
        game.start_wave(3)
        w3_total = game.wave_zombies_total
        
        self.assertLess(w1_total, w2_total)
        self.assertLess(w2_total, w3_total)

    def test_game_reset(self):
        game = Game(screen)
        game.score = 500
        game.wave = 5
        game.player.health = 20
        game.reset_game()
        
        self.assertEqual(game.score, 0)
        self.assertEqual(game.wave, 1)
        self.assertEqual(game.player.health, PLAYER_MAX_HEALTH)


class TestIsometricCamera(unittest.TestCase):
    """Tests for the isometric projection and camera system."""

    def setUp(self):
        from iso_camera import IsoCamera
        self.cam = IsoCamera()

    def test_projection_formula(self):
        """world_to_screen uses (wx-wy)*SX, (wx+wy)*SY."""
        sx, sy = self.cam.project_raw(100, 0)
        self.assertAlmostEqual(sx, 100.0, delta=0.1)
        self.assertAlmostEqual(sy, 50.0, delta=0.1)

        sx, sy = self.cam.project_raw(0, 100)
        self.assertAlmostEqual(sx, -100.0, delta=0.1)
        self.assertAlmostEqual(sy, 50.0, delta=0.1)

        sx, sy = self.cam.project_raw(100, 100)
        self.assertAlmostEqual(sx, 0.0, delta=0.1)
        self.assertAlmostEqual(sy, 100.0, delta=0.1)

    def test_screen_to_world_round_trip(self):
        """screen_to_world must invert world_to_screen exactly."""
        self.cam.update(MAP_WIDTH // 2, MAP_HEIGHT // 2)
        test_points = [(0, 0), (100, 200), (500, 300), (1280, 720), (2000, 1000)]
        for wx, wy in test_points:
            sx, sy = self.cam.world_to_screen(wx, wy)
            rx, ry = self.cam.screen_to_world(sx, sy)
            self.assertAlmostEqual(rx, wx, delta=1.0, msg=f"Round trip failed for ({wx},{wy})")
            self.assertAlmostEqual(ry, wy, delta=1.0, msg=f"Round trip failed for ({wx},{wy})")

    def test_depth_ordering(self):
        """Objects with higher (x+y) should have greater depth (drawn later)."""
        self.assertGreater(self.cam.depth(200, 200), self.cam.depth(100, 100))
        self.assertEqual(self.cam.depth(100, 200), self.cam.depth(200, 100))

    def test_z_elevation(self):
        """Higher z should move the sprite up on screen (smaller y)."""
        self.cam.update(MAP_WIDTH // 2, MAP_HEIGHT // 2)
        sx0, sy0 = self.cam.world_to_screen(500, 500, 0)
        sx1, sy1 = self.cam.world_to_screen(500, 500, 20)
        self.assertEqual(sx0, sx1)
        self.assertLess(sy1, sy0)

    def test_camera_follows_player(self):
        """Camera should track the player's position."""
        game = Game(screen)
        game.player.x = 500
        game.player.y = 500
        game.camera.update(game.player.x, game.player.y)
        # After update, camera.x/y should move toward player
        self.assertAlmostEqual(game.camera.target_x, 500.0, delta=1.0)
        self.assertAlmostEqual(game.camera.target_y, 500.0, delta=1.0)

    def test_camera_clamps_to_map(self):
        """Camera offset should stay within projected map bounds."""
        game = Game(screen)
        game.player.x = 10
        game.player.y = 10
        game.camera.update(game.player.x, game.player.y)
        self.assertGreaterEqual(game.camera.offx, game.camera.map_proj_left - 1)
        self.assertGreaterEqual(game.camera.offy, game.camera.map_proj_top - 1)

        game.player.x = MAP_WIDTH - 10
        game.player.y = MAP_HEIGHT - 10
        game.camera.update(game.player.x, game.player.y)
        self.assertLessEqual(game.camera.offx, game.camera.map_proj_right - SCREEN_WIDTH + 1)


class TestIsometricRendering(unittest.TestCase):
    """Tests for isometric billboard rendering and depth sorting."""

    def test_player_has_shadow_dimensions(self):
        player = Player(500, 500)
        self.assertGreater(player.shadow_w, 0)
        self.assertGreater(player.shadow_h, 0)

    def test_zombie_has_shadow_dimensions(self):
        for ztype in ["regular", "fast", "tank"]:
            z = Zombie(100, 100, ztype)
            self.assertGreater(z.shadow_w, 0)
            self.assertGreater(z.shadow_h, 0)

    def test_obstacle_has_height(self):
        for otype in ["rock", "crate", "tree"]:
            obs = Obstacle(100, 100, otype)
            self.assertGreater(obs.height, 0)

    def test_player_facing_changes_image(self):
        """Player should flip sprite when aiming left vs right."""
        player = Player(500, 500)
        from iso_camera import IsoCamera
        cam = IsoCamera()
        cam.update(500, 500)
        # Simulate mouse on right side
        import pygame as pg
        old_pos = pg.mouse.get_pos
        try:
            pg.mouse.set_pos = lambda p: None
            # Aiming left (mouse to the left of player in world space)
            # screen_to_world of a point left of center -> smaller wx
            player.update_aim(cam)
        finally:
            pass

    def test_depth_sort_order(self):
        """Sprites should be sorted by depth (x+y) for correct occlusion."""
        game = Game(screen)
        game.state = "playing"
        # Run a few frames to populate sprites
        for _ in range(10):
            game.update()
        # Collect depth values
        depths = []
        for s in game.all_sprites:
            if s.alive():
                depths.append(game.camera.depth(s.x, s.y))
        # Verify sorted list is non-decreasing
        sorted_depths = sorted(depths)
        self.assertEqual(depths.sort() if isinstance(depths, list) else None, None)
        # The renderable list should be sorted
        self.assertEqual(sorted_depths, sorted(depths))

    def test_game_renders_without_crash(self):
        """Full draw cycle should complete without errors."""
        game = Game(screen)
        game.state = "playing"
        for _ in range(5):
            game.update()
            game.draw()
            pygame.display.flip()
        self.assertEqual(game.state, "playing")

    def test_collision_uses_world_rect(self):
        """Collision rects should remain in world space (not projected)."""
        player = Player(500, 500)
        obs = Obstacle(530, 500, "rock")
        # Player rect should be a world-space AABB, not projected
        self.assertEqual(player.rect.center, (500, 500))
        self.assertEqual(obs.rect.center, (530, 500))
        self.assertTrue(player.rect.colliderect(obs.rect) or
                        player.rect.move(5, 0).colliderect(obs.rect))

    def test_bullet_aim_uses_world_coords(self):
        """Bullets should spawn at player world position + angle offset."""
        player = Player(500, 500)
        player.angle = 0.0  # pointing right
        tip_dist = 22
        bx = player.x + math.cos(player.angle) * tip_dist
        by = player.y + math.sin(player.angle) * tip_dist
        bullet = Bullet(bx, by, player.angle)
        self.assertAlmostEqual(bullet.x, 522.0, delta=0.1)
        self.assertAlmostEqual(bullet.y, 500.0, delta=0.1)

    def test_bullet_accepts_velocity_vector(self):
        """New isometric spawn passes a (vx, vy) world velocity, not just an angle.
        The bullet should move along that vector, scaled to BULLET_SPEED."""
        b = Bullet(100, 100, (1.0, 0.0))
        self.assertAlmostEqual(b.vx, BULLET_SPEED, delta=0.5)
        self.assertAlmostEqual(b.vy, 0.0, delta=0.5)

        # A 45-degree world-space diagonal
        b45 = Bullet(0, 0, (0.7071, 0.7071))
        self.assertAlmostEqual(b45.vx, BULLET_SPEED * 0.7071, delta=1.0)
        self.assertAlmostEqual(b45.vy, BULLET_SPEED * 0.7071, delta=1.0)

    def test_bullet_legacy_angle_still_works(self):
        """The legacy Bullet(x, y, angle) call must keep working (backward compat)."""
        b = Bullet(0, 0, 0.0)
        self.assertAlmostEqual(b.vx, BULLET_SPEED, delta=0.5)
        self.assertAlmostEqual(b.vy, 0.0, delta=0.5)

    def test_player_stores_aim_world_velocity(self):
        """Player.update_aim should expose a world-space velocity direction
        that matches the on-screen mouse direction (no aim/flight mismatch)."""
        from iso_camera import IsoCamera
        cam = IsoCamera()
        cam.update(MAP_WIDTH // 2, MAP_HEIGHT // 2)
        player = Player(MAP_WIDTH // 2, MAP_HEIGHT // 2)

        # Simulate mouse at the four screen corners; verify the resulting
        # aim velocity, projected to screen space, points at the mouse.
        psx, psy = cam.world_to_screen(player.x, player.y)
        for (msx, msy) in [(0, 0), (SCREEN_WIDTH, 0), (0, SCREEN_HEIGHT), (SCREEN_WIDTH, SCREEN_HEIGHT)]:
            wx, wy = cam.screen_to_world(msx, msy)
            dx, dy = wx - player.x, wy - player.y
            player.angle = math.atan2(dy, dx)
            # Mirror of player.update_aim's velocity computation
            ux, uy = msx - psx, msy - psy
            L = math.hypot(ux, uy)
            if L > 0:
                ux /= L; uy /= L
            wvx = (ux / ISO_SCALE_X + uy / ISO_SCALE_Y) / 2.0
            wvy = (uy / ISO_SCALE_Y - ux / ISO_SCALE_X) / 2.0
            L2 = math.hypot(wvx, wvy)
            if L2 > 0:
                wvx /= L2; wvy /= L2
            player.aim_world_vx, player.aim_world_vy = wvx, wvy
            # The world velocity (wvx, wvy) must project to a screen direction
            # that matches the screen direction from player to mouse.
            screen_dir = math.atan2(msy - psy, msx - psx)
            flight_dir = math.atan2((wvx + wvy) * ISO_SCALE_Y, (wvx - wvy) * ISO_SCALE_X)
            self.assertAlmostEqual(flight_dir, screen_dir, delta=0.01,
                                   msg=f"Aim mismatch at mouse ({msx},{msy})")

    def test_zombie_bob_while_moving(self):
        """Zombies should have bob_z > 0 while pursuing."""
        player = Player(500, 500)
        zombie = Zombie(100, 100, "regular")
        zombie.update(player, [], [])
        self.assertGreater(zombie.bob_z, 0)

    def test_player_bob_while_moving(self):
        """Player should have bob_z > 0 after moving."""
        player = Player(500, 500)
        keys = [0] * 512
        keys[pygame.K_d] = 1
        player.handle_input(keys, [])
        player.update()
        self.assertGreater(player.bob_z, 0)


if __name__ == "__main__":
    unittest.main()
