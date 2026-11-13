"""Headless unit tests for the new survival and horror systems."""
import unittest

from systems.survival import SurvivalSystem
from systems.storytelling import StorySystem
from systems.horror_director import HorrorDirector
from systems.horde_director import HordeDirector


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

    def test_crafting_uses_scrap_and_heals_player(self):
        system = SurvivalSystem()
        player = type("Player", (), {"hp": 40.0, "max_hp": 100.0})()
        system.add_scrap(3)
        self.assertTrue(system.craft_medkit(player))
        self.assertEqual(system.scrap, 0)
        self.assertEqual(player.hp, 75.0)
        self.assertFalse(system.craft_medkit(player))

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


class FakePlayer:
    x = 24.0
    y = 24.0
    hp = 100.0
    max_hp = 100.0


class FakeProgression:
    time = 240.0
    message = ""
    def notify(self, message, hold=3.0):
        self.message = message


class FakeZombie:
    alive = True
    spawning = False
    def __init__(self, x=30.0, y=24.0):
        self.x, self.y = x, y
    def dist(self, player):
        return ((self.x-player.x)**2 + (self.y-player.y)**2)**0.5


class FakeGrid:
    def is_blocked(self, x, y):
        return False


class FakeController:
    w = h = 48
    grid = FakeGrid()
    _spawn_points = [(3, 3), (44, 3), (3, 44), (44, 44),
                     (24, 5), (5, 24), (43, 24), (24, 43)]
    zombies = []
    @property
    def alive_count(self):
        return len(self.zombies)
    def add_zombie(self, unused, x, y, ztype):
        self.zombies.append(FakeZombie(x, y))


class TestHordeDirector(unittest.TestCase):
    def test_sustained_gunfire_attracts_a_delayed_horde(self):
        director = HordeDirector(seed=4)
        controller = FakeController()
        controller.zombies = []
        spawned = 0
        for _ in range(12):
            spawned += director.update(0.25, FakePlayer(), controller,
                                       240.0, 19.0, 1.0)
        self.assertGreater(spawned, 0)
        self.assertGreaterEqual(len(controller.zombies), 1)
        self.assertEqual(director.hordes_spawned, 1)

    def test_quiet_player_does_not_trigger_horde(self):
        director = HordeDirector(seed=2)
        controller = FakeController()
        controller.zombies = []
        for _ in range(20):
            self.assertEqual(director.update(0.25, FakePlayer(), controller,
                                             120.0, 0.0, 0.0), 0)

    def test_horde_spawns_are_not_adjacent_to_player(self):
        director = HordeDirector(seed=8)
        controller = FakeController()
        controller.zombies = []
        for _ in range(12):
            director.update(0.25, FakePlayer(), controller, 240.0, 19.0, 1.0)
        for zombie in controller.zombies:
            self.assertGreaterEqual(zombie.dist(FakePlayer()), 8.0)

    def test_active_population_is_bounded(self):
        director = HordeDirector(seed=8)
        controller = FakeController()
        controller.zombies = [FakeZombie() for _ in range(29)]
        for _ in range(12):
            director.update(0.25, FakePlayer(), controller, 600.0, 19.0, 1.0)
        self.assertLessEqual(controller.alive_count, 30)


class TestHorrorDirector(unittest.TestCase):
    def test_director_emits_suspense_event(self):
        director = HorrorDirector(seed=1)
        director.event_timer = 0.01
        progression = FakeProgression()
        message = director.update(0.1, FakePlayer(), FakeController(),
                                  progression)
        self.assertIsNotNone(message)
        self.assertEqual(progression.message, message)

    def test_recovery_reduces_target_intensity(self):
        director = HorrorDirector(seed=1)
        controller = FakeController()
        controller.zombies = [FakeZombie(25, 24) for _ in range(5)]
        player = FakePlayer()
        for _ in range(120):
            director.update(0.1, player, controller, FakeProgression())
        before = director.tension
        director.begin_recovery(20.0)
        for _ in range(30):
            director.update(0.1, player, controller, FakeProgression())
        self.assertLess(director.tension, before)

    def test_close_attack_delays_extra_scare(self):
        director = HorrorDirector(seed=1)
        director.event_timer = 0.01
        controller = FakeController()
        controller.zombies = [FakeZombie(25, 24) for _ in range(4)]
        message = director.update(0.1, FakePlayer(), controller,
                                  FakeProgression())
        self.assertIsNone(message)


if __name__ == "__main__":
    unittest.main()
