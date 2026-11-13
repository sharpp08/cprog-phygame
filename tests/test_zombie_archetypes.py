"""Tests for special zombie archetypes and damage profiles."""
import unittest

import config
from entities.zombie import Zombie


class TestZombieArchetypes(unittest.TestCase):
    def test_screamer_has_distinct_detection_and_alert_profile(self):
        screamer = Zombie(10.0, 10.0, "screamer")
        regular = Zombie(10.0, 10.0, "regular")
        self.assertGreater(screamer.detect, regular.detect)
        self.assertLess(screamer.damage, regular.damage)
        self.assertEqual(config.ZOMBIE_TYPES["screamer"]["label"], "Screamer")

    def test_chase_speed_accelerates_gradually(self):
        class OpenGrid:
            def move_circle(self, pos, delta, radius):
                return pos[0] + delta[0], pos[1] + delta[1]
        zombie = Zombie(2.0, 2.0, "regular")
        zombie.spawning = False
        zombie.state = "pursue"
        initial = zombie._speed_current
        zombie.apply_move(1.0, 0.0, 0.1, OpenGrid())
        self.assertGreater(zombie._speed_current, initial)
        self.assertLess(zombie._speed_current, zombie.speed)

    def test_all_infected_archetypes_enter_their_run_cycle_when_chasing(self):
        for ztype in config.ZOMBIE_TYPES:
            with self.subTest(ztype=ztype):
                zombie = Zombie(10.0, 10.0, ztype)
                zombie.spawning = False
                zombie.state = "pursue"
                zombie.moving = True
                zombie._actual_speed = zombie.speed
                zombie.update(1.0 / 60.0)
                self.assertEqual(zombie.anim_state, "run")

    def test_stalker_has_a_distinct_stealth_profile(self):
        stalker = Zombie(10.0, 10.0, "stalker")
        regular = Zombie(10.0, 10.0, "regular")
        self.assertNotEqual(stalker.speed, regular.speed)
        self.assertLess(stalker.detect, regular.detect)
        self.assertEqual(config.ZOMBIE_TYPES["stalker"]["label"], "Stalker")

    def test_armored_zombie_reduces_incoming_damage(self):
        armored = Zombie(10.0, 10.0, "armored")
        before = armored.hp
        armored.on_hit(100.0, None)
        self.assertAlmostEqual(before - armored.hp, 58.0)
        self.assertTrue(armored.alive)

    def test_armored_zombie_is_slower_and_tougher_than_regular(self):
        armored = Zombie(10.0, 10.0, "armored")
        regular = Zombie(10.0, 10.0, "regular")
        self.assertGreater(armored.max_hp, regular.max_hp)
        self.assertLess(armored.speed, regular.speed)


if __name__ == "__main__":
    unittest.main()
