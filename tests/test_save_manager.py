"""Regression tests for safe, portable save-game persistence."""
import json

import config
import tempfile
import unittest
from types import SimpleNamespace

from systems.save_manager import SaveManager, SAVE_VERSION


class SaveManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = SaveManager(self.temp.name)
        self.player = SimpleNamespace(to_dict=lambda: {
            "x": 4.5, "y": 8.25, "hp": 80, "weapons": []})
        self.progression = SimpleNamespace(
            phase="explore", state="playing", score=10, kills=1,
            time=12.5, wave=0, shrine_reached=False)
        self.settings = {"master": 0.8}

    def tearDown(self):
        self.temp.cleanup()

    def test_round_trip_creates_resumable_save(self):
        self.assertTrue(self.manager.save(
            self.player, self.progression, self.settings))
        data = self.manager.load()
        self.assertIsNotNone(data)
        self.assertEqual(data["player"]["hp"], 80)
        self.assertEqual(data["settings"]["master"], 0.8)
        self.assertEqual(data["world"]["width"], config.MAP_W)
        self.assertEqual(data["world"]["height"], config.MAP_H)

    def test_corrupt_save_is_rejected(self):
        with open(self.manager.path, "w", encoding="utf-8") as handle:
            handle.write("{broken")
        self.assertIsNone(self.manager.load())

    def test_dead_player_save_is_not_resumable(self):
        dead = SimpleNamespace(to_dict=lambda: {
            "x": 4, "y": 8, "hp": 0, "weapons": []})
        self.assertTrue(self.manager.save(dead, self.progression, self.settings))
        self.assertIsNone(self.manager.load())

    def test_invalid_nested_shapes_are_rejected(self):
        with open(self.manager.path, "w", encoding="utf-8") as handle:
            json.dump({"version": SAVE_VERSION, "player": [],
                       "progression": {}}, handle)
        self.assertIsNone(self.manager.load())

    def test_delete_is_idempotent(self):
        self.manager.delete()
        self.manager.delete()
        self.assertFalse(self.manager.has_save())


if __name__ == "__main__":
    unittest.main()