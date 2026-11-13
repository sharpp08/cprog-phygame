"""Headless tests for survival resources, story, pacing and horde pressure."""
import unittest
from types import SimpleNamespace

from systems.horde_director import HordeDirector
from systems.horror_director import HorrorDirector
from systems.inventory import apply_pickup
from systems.storytelling import StorySystem
from systems.survival import SurvivalSystem


class FakeWorld:
    shrine = (24, 24)
    ruin = (36, 36)
    waterfall = (26, 33)
    start = (6, 43)


class PlayerForDirector:
    x = 24.0
    y = 24.0
    hp = 100.0
    max_hp = 100.0
    weapons = []


class ProgressionForDirector:
    time = 240.0
    message = ""
    def notify(self, message, hold=3.0):
        self.message = message


class ZombieForDirector:
    alive = True
    spawning = False
    def __init__(self, x=30.0, y=24.0):
        self.x, self.y = x, y
    def dist(self, player):
        return ((self.x - player.x) ** 2 + (self.y - player.y) ** 2) ** 0.5


class GridForHorde:
    def is_blocked(self, x, y):
        return False


class ControllerForHorde:
    w = h = 48
    grid = GridForHorde()
    _spawn_points = [(3, 3), (44, 3), (3, 44), (44, 44),
                     (24, 5), (5, 24), (43, 24), (24, 43)]
    def __init__(self, zombies=None):
        self.zombies = list(zombies or [])
    @property
    def alive_count(self):
        return len(self.zombies)
    def add_zombie(self, unused, x, y, ztype):
        self.zombies.append(ZombieForDirector(x, y))


class TestSurvival(unittest.TestCase):
    def test_flashlight_drains_without_passive_recharge(self):
        system = SurvivalSystem()
        system.update(10.0, False)
        self.assertLess(system.flashlight_battery, 100.0)
        system.toggle_flashlight()
        before = system.flashlight_battery
        system.update(10.0, False)
        self.assertEqual(system.flashlight_battery, before)

    def test_battery_replacement_consumes_spare_cell(self):
        system = SurvivalSystem()
        system.flashlight_battery = 12.0
        self.assertTrue(system.replace_battery())
        self.assertEqual(system.flashlight_battery, 100.0)
        self.assertEqual(system.battery_cells, 1)
        self.assertTrue(system.flashlight_on)

    def test_battery_cannot_be_replaced_without_spare_cells(self):
        system = SurvivalSystem()
        system.battery_cells = 0
        system.flashlight_battery = 10.0
        self.assertFalse(system.replace_battery())

    def test_battery_pickup_adds_cell_to_inventory(self):
        system = SurvivalSystem()
        pickup = SimpleNamespace(ptype="battery", value=1, taken=False, spec={})
        apply_pickup(SimpleNamespace(), pickup, survival=system)
        self.assertEqual(system.battery_cells, 3)
        self.assertTrue(pickup.taken)

    def test_empty_battery_forces_light_off(self):
        system = SurvivalSystem()
        system.flashlight_battery = 0.1
        system.update(1.0, False)
        self.assertFalse(system.flashlight_on)

    def test_sprint_consumes_stamina(self):
        system = SurvivalSystem()
        system.update(1.0, True)
        self.assertLess(system.stamina, 100.0)

    def test_crafting_uses_scrap_and_heals_player(self):
        system = SurvivalSystem()
        player = SimpleNamespace(hp=40.0, max_hp=100.0)
        system.add_scrap(3)
        self.assertTrue(system.craft_medkit(player))
        self.assertEqual(system.scrap, 0)
        self.assertEqual(player.hp, 75.0)
        self.assertFalse(system.craft_medkit(player))


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
        progression = ProgressionForDirector()
        message = director.update(
            0.1, PlayerForDirector(), ControllerForHorde(
                [ZombieForDirector(28, 24)]), progression)
        self.assertIsNotNone(message)
        self.assertEqual(progression.message, message)

    def test_recovery_reduces_target_intensity(self):
        director = HorrorDirector(seed=1)
        controller = ControllerForHorde(
            [ZombieForDirector(25, 24) for _ in range(5)])
        player = PlayerForDirector()
        for _ in range(120):
            director.update(0.1, player, controller, ProgressionForDirector())
        before = director.tension
        director.begin_recovery(20.0)
        for _ in range(30):
            director.update(0.1, player, controller, ProgressionForDirector())
        self.assertLess(director.tension, before)

    def test_close_attack_delays_extra_scare(self):
        director = HorrorDirector(seed=1)
        director.event_timer = 0.01
        controller = ControllerForHorde(
            [ZombieForDirector(25, 24) for _ in range(4)])
        message = director.update(
            0.1, PlayerForDirector(), controller, ProgressionForDirector())
        self.assertIsNone(message)


class TestHordeDirector(unittest.TestCase):
    def test_sustained_gunfire_attracts_a_delayed_horde(self):
        director = HordeDirector(seed=4)
        controller = ControllerForHorde()
        spawned = 0
        for _ in range(12):
            spawned += director.update(
                0.25, PlayerForDirector(), controller, 240.0, 19.0, 1.0)
        self.assertGreater(spawned, 0)
        self.assertGreaterEqual(len(controller.zombies), 1)
        self.assertEqual(director.hordes_spawned, 1)

    def test_quiet_player_does_not_trigger_horde(self):
        director = HordeDirector(seed=2)
        controller = ControllerForHorde()
        for _ in range(20):
            self.assertEqual(director.update(
                0.25, PlayerForDirector(), controller, 120.0, 0.0, 0.0), 0)

    def test_horde_spawns_are_not_adjacent_to_player(self):
        director = HordeDirector(seed=8)
        controller = ControllerForHorde()
        for _ in range(12):
            director.update(
                0.25, PlayerForDirector(), controller, 240.0, 19.0, 1.0)
        for zombie in controller.zombies:
            self.assertGreaterEqual(zombie.dist(PlayerForDirector()), 8.0)

    def test_active_population_is_bounded(self):
        director = HordeDirector(seed=8)
        controller = ControllerForHorde(
            [ZombieForDirector() for _ in range(29)])
        for _ in range(12):
            director.update(
                0.25, PlayerForDirector(), controller, 600.0, 19.0, 1.0)
        self.assertLessEqual(controller.alive_count, 30)


if __name__ == "__main__":
    unittest.main()
