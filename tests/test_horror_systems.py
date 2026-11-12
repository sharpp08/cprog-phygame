"""Headless unit tests for the new survival and horror systems."""
import unittest

from systems.survival import SurvivalSystem
from systems.storytelling import StorySystem
from systems.horror_director import HorrorDirector


class FakeWorld:
    shrine = (24, 24)
    ruin = (36, 36)
    waterfall = (26, 33)
    start = (6, 43)


class FakePlayer:
    hp = 100
    max_hp = 100


class FakeProgression:
    time = 20.0
    message = ""
    def notify(self, message, hold=3.5):
        self.message = message


class FakeZombie:
    alive = True
    def dist(self, player):
        return 4.0


class FakeController:
    zombies = [FakeZombie()]


class TestSurvival(unittest.TestCase):
    def test_flashlight_drains_and_recharges(self):
        system = SurvivalSystem()
        system.update(10.0, False)
        self.assertLess(system.flashlight_battery, 100.0)
        system.toggle_flashlight()
        before = system.flashlight_battery
        system.update(10.0, False)
        self.assertGreater(system.flashlight_battery, before)

    def test_sprint_consumes_stamina(self):
        system = SurvivalSystem()
        system.update(1.0, True)
        self.assertLess(system.stamina, 100.0)

    def test_empty_battery_forces_light_off(self):
        system = SurvivalSystem()
        system.flashlight_battery = 0.1
        system.update(1.0, False)
        self.assertFalse(system.flashlight_on)


class TestStory(unittest.TestCase):
    def test_clue_can_only_be_collected_once(self):
        story = StorySystem(FakeWorld())
        clue = story.clues[0]
        x, y = clue["pos"]
        self.assertIsNotNone(story.interact(x, y))
        self.assertIsNone(story.interact(x, y))

    def test_ending_tiers(self):
        story = StorySystem(FakeWorld())
        self.assertEqual(story.ending()[0], "THE ESCAPE")
        story.discovered.update((0, 1))
        self.assertEqual(story.ending()[0], "THE SURVIVOR")
        story.discovered.update((2, 3))
        self.assertEqual(story.ending()[0], "THE WITNESS")


class TestHorrorDirector(unittest.TestCase):
    def test_director_emits_an_event(self):
        director = HorrorDirector(seed=1)
        director.event_timer = 0.01
        progression = FakeProgression()
        message = director.update(0.1, FakePlayer(), FakeController(),
                                  progression)
        self.assertIsNotNone(message)
        self.assertEqual(progression.message, message)


if __name__ == "__main__":
    unittest.main()
