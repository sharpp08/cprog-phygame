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
