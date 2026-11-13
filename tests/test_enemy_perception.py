"""Tests for line-of-sight, darkness and crouch-based zombie detection."""
import unittest
from types import SimpleNamespace

from systems.enemy_ai import ZombieController


class Grid:
    def __init__(self):
        self.blocked = set()
    def is_blocked(self, x, y):
        return (x, y) in self.blocked


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

    def test_rain_reduces_detection_range(self):
        self.controller.rain_amount = 1.0
        self.assertFalse(self.controller._can_see_player(
            self.zombie, self.player, 11.0))


if __name__ == "__main__":
    unittest.main()
