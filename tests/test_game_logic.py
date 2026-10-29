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

if __name__ == "__main__":
    unittest.main()
