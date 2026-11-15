"""Regression tests for grounded player movement and stamina behaviour."""
import unittest

from entities.player import Player
from systems.survival import SurvivalSystem


class OpenGrid:
    def move_circle(self, pos, delta, radius):
        return pos[0] + delta[0], pos[1] + delta[1]


class XBlockedGrid:
    """Resolve horizontal movement but allow vertical wall sliding."""
    def move_circle(self, pos, delta, radius):
        return pos[0], pos[1] + delta[1]


class TestGroundedPlayerMovement(unittest.TestCase):
    def test_acceleration_is_smooth(self):
        player = Player(2.0, 2.0)
        player.apply_movement((1.0, 0.0), False, 1.0 / 60.0, OpenGrid())
        self.assertGreater(player.actual_speed, 0.0)
        self.assertLess(player.actual_speed, 3.2)

    def test_release_brakes_instead_of_snapping_to_zero(self):
        player = Player(2.0, 2.0)
        for _ in range(20):
            player.apply_movement((1.0, 0.0), False, 1.0 / 60.0, OpenGrid())
        before = player.actual_speed
        player.apply_movement((0.0, 0.0), False, 1.0 / 60.0, OpenGrid())
        self.assertGreater(player.actual_speed, 0.0)
        self.assertLess(player.actual_speed, before)

    def test_collision_feedback_removes_blocked_axis_velocity(self):
        player = Player(2.0, 2.0)
        player.apply_movement((1.0, 1.0), False, 1.0 / 30.0, XBlockedGrid())
        self.assertAlmostEqual(player._velocity[0], 0.0, places=7)
        self.assertGreater(player._velocity[1], 0.0)
        self.assertAlmostEqual(player.actual_speed, abs(player._velocity[1]), places=7)

    def test_fully_blocked_movement_cannot_build_velocity_or_gait(self):
        class BlockedGrid:
            def move_circle(self, pos, delta, radius):
                return pos

        player = Player(2.0, 2.0)
        for _ in range(10):
            player.apply_movement((1.0, 0.0), True, 1.0 / 60.0, BlockedGrid())
        self.assertEqual(player._velocity, (0.0, 0.0))
        self.assertEqual(player._gait, 0.0)
        self.assertFalse(player.footstep_sound)

    def test_sprint_locks_at_low_stamina_until_recovered(self):
        survival = SurvivalSystem()
        survival.stamina = 5.5
        can_run = survival.update(0.1, True)
        self.assertFalse(can_run)
        self.assertTrue(survival._sprint_locked)
        exhausted_value = survival.stamina

        # Holding sprint must not cause rapid drain/recharge oscillation.
        for _ in range(8):
            self.assertFalse(survival.update(0.1, True))
        self.assertAlmostEqual(survival.stamina, exhausted_value)

        # Releasing sprint allows recovery; it unlocks only at the upper threshold.
        for _ in range(4):
            self.assertFalse(survival.update(0.25, False))
        self.assertTrue(survival._sprint_locked)
        self.assertTrue(survival.update(0.25, False))
        self.assertFalse(survival._sprint_locked)


if __name__ == "__main__":
    unittest.main()
