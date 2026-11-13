"""Regression tests for distance-synchronised procedural animation."""
import unittest

from entities.player import Player
from entities.weapon import Weapon
from entities.zombie import Zombie


class OpenGrid:
    def move_circle(self, pos, delta, radius):
        return pos[0] + delta[0], pos[1] + delta[1]


class BlockedGrid:
    def move_circle(self, pos, delta, radius):
        return pos


class TestPlayerAnimation(unittest.TestCase):
    def test_blocked_player_does_not_foot_slide(self):
        player = Player(2.0, 2.0)
        gait = player._gait
        player.apply_movement((1.0, 0.0), False, 0.25, BlockedGrid())
        player.update(0.25)
        self.assertEqual(player._gait, gait)
        self.assertEqual(player.actual_speed, 0.0)
        self.assertFalse(player.footstep_sound)

    def test_gait_uses_actual_distance(self):
        player = Player(2.0, 2.0)
        player.apply_movement((1.0, 0.0), False, 0.1, OpenGrid())
        self.assertGreater(player._gait, 0.0)
        self.assertGreater(player.actual_speed, 0.0)

    def test_state_change_starts_blend(self):
        player = Player(2.0, 2.0)
        player.apply_movement((1.0, 0.0), True, 0.2, OpenGrid())
        player.update(0.016)
        self.assertIn(player.anim_state, ("walk", "run"))
        self.assertLess(player.anim_blend, 1.0)
        player.update(0.2)
        self.assertEqual(player.anim_blend, 1.0)

    def test_reload_progress_is_monotonic(self):
        weapon = Weapon("pistol")
        weapon.mag = 1
        self.assertTrue(weapon.start_reload())
        start = weapon.reload_progress
        weapon.update(weapon.spec["reload_time"] * 0.5)
        self.assertGreater(weapon.reload_progress, start)


class TestZombieAnimation(unittest.TestCase):
    def test_blocked_zombie_does_not_advance_walk_cycle(self):
        zombie = Zombie(2.0, 2.0)
        zombie.spawning = False
        gait = zombie._gait
        zombie.apply_move(1.0, 0.0, 0.2, BlockedGrid())
        zombie.update(0.2)
        self.assertEqual(zombie._gait, gait)
        self.assertFalse(zombie.moving)

    def test_zombie_types_have_distinct_motion_profiles(self):
        runner = Zombie(2.0, 2.0, "fast")
        tank = Zombie(2.0, 2.0, "tank")
        self.assertNotEqual(runner._gait_rate, tank._gait_rate)
        self.assertGreater(runner._gait_stretch, tank._gait_stretch)


if __name__ == "__main__":
    unittest.main()
