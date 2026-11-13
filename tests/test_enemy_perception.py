"""Tests for line-of-sight, darkness and crouch-based zombie detection."""
import unittest
from types import SimpleNamespace

from systems.enemy_ai import ZombieController


class Grid:
    def __init__(self):
        self.blocked = set()
    def is_blocked(self, x, y):
        return (x, y) in self.blocked
    def move_circle(self, pos, delta, radius):
        return pos[0] + delta[0], pos[1] + delta[1]


class Nav:
    def plan(self, zombie):
        zombie.path = [(int(zombie.x), int(zombie.y))]
        zombie.path_i = 0
    def velocity(self, zombie, target_x, target_y):
        return (1.0, 0.0)


class TestZombiePerception(unittest.TestCase):
    def setUp(self):
        self.grid = Grid()
        self.controller = ZombieController(self.grid, None, 48, 48)
        self.zombie = SimpleNamespace(x=5.0, y=5.0, detect=12.0,
                                      dist=lambda player: 8.0)
        self.player = SimpleNamespace(x=13.0, y=5.0,
                                      flashlight_on=True, crouching=False)

    def test_clear_line_of_sight_detects_player(self):
        self.assertTrue(self.controller._can_see_player(
            self.zombie, self.player, 8.0))

    def test_solid_geometry_blocks_sight(self):
        self.grid.blocked.add((9, 5))
        self.assertFalse(self.controller._can_see_player(
            self.zombie, self.player, 8.0))

    def test_flashlight_off_reduces_detection_range(self):
        self.player.flashlight_on = False
        self.assertFalse(self.controller._can_see_player(
            self.zombie, self.player, 8.5))

    def test_crouching_reduces_detection_range(self):
        self.player.crouching = True
        self.assertFalse(self.controller._can_see_player(
            self.zombie, self.player, 8.0))


    def test_noise_causes_investigation_before_player_detection(self):
        from entities.zombie import Zombie
        controller = ZombieController(self.grid, Nav(), 48, 48)
        controller.set_context(self.player, None, None, [], world=None)
        self.player.x, self.player.y = 30.0, 30.0
        zombie = Zombie(5.0, 5.0, "regular")
        zombie.spawning = False
        zombie._repath_cd = 0.5
        controller.zombies = [zombie]
        controller.emit_noise(6.0, 5.0, 9.0, 2.0)
        controller._behaviour(zombie, 0.016, self.player)
        self.assertEqual(zombie.state, "investigating")

    def test_stalker_uses_last_known_position_after_losing_sight(self):
        from entities.zombie import Zombie
        controller = ZombieController(self.grid, Nav(), 48, 48)
        controller.set_context(self.player, None, None, [], world=None)
        self.player.x, self.player.y = 30.0, 30.0
        self.player.flashlight_on = False
        zombie = Zombie(5.0, 5.0, "stalker")
        zombie.spawning = False
        zombie.search_timer = 2.0
        zombie.last_known = (12.0, 5.0)
        controller.zombies = [zombie]
        controller._behaviour(zombie, 0.016, self.player)
        self.assertEqual(zombie.state, "stalking")

    def test_rain_reduces_detection_range(self):
        self.controller.rain_amount = 1.0
        self.assertFalse(self.controller._can_see_player(
            self.zombie, self.player, 11.0))


if __name__ == "__main__":
    unittest.main()
