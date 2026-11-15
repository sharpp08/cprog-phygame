"""Regression tests for shared character gait and enemy motion physics."""
import unittest

import config
from engine.asset_manager import AssetManager
from entities.zombie import Zombie


class OpenGrid:
    def move_circle(self, pos, delta, radius):
        return pos[0] + delta[0], pos[1] + delta[1]


class XBlockedGrid:
    def move_circle(self, pos, delta, radius):
        return pos[0], pos[1] + delta[1]


class CharacterPhysicsTests(unittest.TestCase):
    def test_gait_has_sixty_percent_stance_and_forty_percent_swing(self):
        samples = 1000
        stance = sum(
            AssetManager._gait_leg_pose(i / samples, 1.0, 1.0)[1] == 0.0
            for i in range(samples)
        )
        self.assertAlmostEqual(stance / samples, 0.60, delta=0.002)

    def test_opposite_feet_have_a_double_support_interval(self):
        left = AssetManager._gait_leg_pose(0.05, 1.0, 1.0)
        right = AssetManager._gait_leg_pose(0.55, 1.0, 1.0)
        self.assertEqual(left[1], 0.0)
        self.assertEqual(right[1], 0.0)

    def test_swing_foot_lifts_smoothly(self):
        start = AssetManager._gait_leg_pose(0.60, 1.0, 5.0)
        middle = AssetManager._gait_leg_pose(0.80, 1.0, 5.0)
        end = AssetManager._gait_leg_pose(1.00, 1.0, 5.0)
        self.assertEqual(start[1], 0.0)
        self.assertGreater(middle[1], 0.0)
        self.assertAlmostEqual(end[1], 0.0, places=6)

    def test_all_enemy_types_turn_with_inertia(self):
        for ztype in config.ZOMBIE_TYPES:
            with self.subTest(ztype=ztype):
                zombie = Zombie(5.0, 5.0, ztype)
                zombie.spawning = False
                zombie.state = "pursue"
                zombie._stumble = 20.0
                for _ in range(24):
                    zombie.apply_move(1.0, 0.0, 1.0 / 60.0, OpenGrid())
                self.assertGreater(zombie._velocity[0], 0.0)
                zombie.apply_move(0.0, 1.0, 1.0 / 60.0, OpenGrid())
                self.assertGreater(zombie._velocity[0], 0.0)
                self.assertGreater(zombie._velocity[1], 0.0)

    def test_enemy_brakes_gradually_when_target_direction_disappears(self):
        zombie = Zombie(5.0, 5.0, "regular")
        zombie.spawning = False
        zombie.state = "pursue"
        zombie._stumble = 20.0
        for _ in range(30):
            zombie.apply_move(1.0, 0.0, 1.0 / 60.0, OpenGrid())
        before = zombie._actual_speed
        zombie.apply_move(0.0, 0.0, 1.0 / 60.0, OpenGrid())
        self.assertGreater(zombie._actual_speed, 0.0)
        self.assertLess(zombie._actual_speed, before)

    def test_collision_feedback_preserves_wall_slide_and_clears_blocked_axis(self):
        zombie = Zombie(5.0, 5.0, "regular")
        zombie.spawning = False
        zombie.state = "pursue"
        zombie._stumble = 20.0
        zombie.apply_move(1.0, 1.0, 1.0 / 30.0, XBlockedGrid())
        self.assertAlmostEqual(zombie._velocity[0], 0.0, places=7)
        self.assertGreater(zombie._velocity[1], 0.0)

    def test_projectile_recoil_uses_the_impact_direction(self):
        zombie = Zombie(5.0, 5.0, "regular")
        zombie.spawning = False
        zombie._stumble = 20.0
        zombie.on_hit(1.0, None, knock_dir=(0.0, -1.0))
        zombie.apply_move(0.0, 0.0, 0.1, OpenGrid())
        self.assertAlmostEqual(zombie.x, 5.0, places=7)
        self.assertLess(zombie.y, 5.0)

    def test_ai_speed_scalars_are_not_lost_during_velocity_normalization(self):
        slow = Zombie(5.0, 5.0, "regular")
        fast = Zombie(5.0, 5.0, "regular")
        for zombie in (slow, fast):
            zombie.spawning = False
            zombie.state = "pursue"
            zombie._stumble = 20.0
        for _ in range(90):
            slow.apply_move(0.45, 0.0, 1.0 / 60.0, OpenGrid())
            fast.apply_move(1.0, 0.0, 1.0 / 60.0, OpenGrid())
        self.assertLess(slow._actual_speed, fast._actual_speed)

    def test_exactly_overlapping_enemies_receive_separation_steering(self):
        from systems.enemy_ai import ZombieController
        controller = ZombieController(OpenGrid(), None, 20, 20)
        first = Zombie(5.0, 5.0, "regular")
        second = Zombie(5.0, 5.0, "regular")
        first.spawning = second.spawning = False
        controller.zombies = [first, second]
        sx, sy = controller._separation(first, 1.0 / 60.0)
        self.assertGreater((sx * sx + sy * sy) ** 0.5, 0.0)


if __name__ == "__main__":
    unittest.main()
