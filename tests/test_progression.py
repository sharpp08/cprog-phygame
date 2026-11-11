"""Unit tests for the survival progression system.

These run headlessly (no display) by setting the SDL dummy video/audio
drivers before pygame is imported.

Run with:  python -m unittest tests.test_progression
"""
from __future__ import annotations

import os
import sys
import unittest

# Headless mode: must be set before pygame is imported.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from systems.progression import Progression


class FakePlayer:
    """Minimal player stand-in for progression tests."""

    def __init__(self, x: float, y: float, hp: float = 100.0) -> None:
        self.x = x
        self.y = y
        self.hp = hp
        self.max_hp = 100.0

    @property
    def dead(self) -> bool:
        return self.hp <= 0


class FakeController:
    """Minimal zombie controller stand-in: counts spawned zombies."""

    def __init__(self) -> None:
        self.zombies = []
        self._spawn_calls = 0

    @property
    def alive_count(self) -> int:
        return len(self.zombies)

    def add_zombie(self, _z, x, y, ztype="regular"):
        self._spawn_calls += 1
        self.zombies.append({"x": x, "y": y, "type": ztype})
        return {"x": x, "y": y, "type": ztype}

    def spawn_random(self):
        return None

    def spawn_near(self, pos):
        return self.add_zombie(None, pos[0], pos[1], "regular")

    def kill(self, z):
        self.zombies.remove(z)


class FakeWorld:
    """Minimal world stand-in for wave spawn placement."""

    def __init__(self):
        self.shrine = config.SHRINE_POS

    def spawn_wave_around_shrine(self, count):
        out = []
        sx, sy = self.shrine
        for i in range(count):
            out.append((sx + 3 + i, sy, "regular"))
        return out


class TestProgression(unittest.TestCase):
    # ------------------------------------------------------------------
    def test_initial_state(self):
        prog = Progression()
        self.assertEqual(prog.phase, "explore")
        self.assertEqual(prog.state, "playing")
        self.assertEqual(prog.score, 0)
        self.assertEqual(prog.kills, 0)
        self.assertEqual(prog.wave, 0)

    # ------------------------------------------------------------------
    def test_on_kill_tracks_score_and_kills(self):
        prog = Progression()

        class FakeZombie:
            score = 18

        prog.on_kill(FakeZombie())
        self.assertEqual(prog.score, 18)
        self.assertEqual(prog.kills, 1)

    # ------------------------------------------------------------------
    def test_check_lose_transitions_state(self):
        prog = Progression()
        player = FakePlayer(5, 5, hp=0.0)
        self.assertTrue(prog.check_lose(player))
        self.assertEqual(prog.state, "lost")

    def test_check_lose_false_when_alive(self):
        prog = Progression()
        player = FakePlayer(5, 5, hp=100.0)
        self.assertFalse(prog.check_lose(player))
        self.assertEqual(prog.state, "playing")

    # ------------------------------------------------------------------
    def test_shrine_reach_starts_first_wave(self):
        """Reaches the shrine, which should transition to the shrine
        phase and start wave 1 without raising."""
        prog = Progression()
        controller = FakeController()
        world = FakeWorld()

        # Place player just inside the shrine trigger radius (3.5 tiles).
        sx, sy = config.SHRINE_POS
        player = FakePlayer(sx + 1.0, sy + 1.0)  # ~1.4 tiles away

        prog.update(0.1, player, controller, world)

        self.assertEqual(prog.phase, "shrine")
        self.assertTrue(prog.shrine_reached)
        self.assertEqual(prog.wave, 1)
        # Wave 1 spawns WAVE_BASE_COUNT * WAVE_GROWTH^0 = 8 zombies.
        self.assertEqual(controller.alive_count, config.WAVE_BASE_COUNT)
        self.assertEqual(controller._spawn_calls, config.WAVE_BASE_COUNT)

    # ------------------------------------------------------------------
    def test_shrine_phase_advances_waves(self):
        prog = Progression()
        controller = FakeController()
        world = FakeWorld()

        # Force into shrine phase with wave 1 already done.
        prog.phase = "shrine"
        prog.wave = 1
        prog.shrine_reached = True

        # Clear all zombies -> should start wave 2.
        controller.zombies = []
        prog.update(0.1, FakePlayer(*config.SHRINE_POS), controller, world)
        self.assertEqual(prog.wave, 2)
        expected = int(config.WAVE_BASE_COUNT *
                       (config.WAVE_GROWTH ** (prog.wave - 1)))
        self.assertEqual(controller.alive_count, expected)

    # ------------------------------------------------------------------
    def test_win_after_final_wave_cleared(self):
        prog = Progression()
        controller = FakeController()
        world = FakeWorld()

        prog.phase = "shrine"
        prog.wave = config.WAVES_AT_SHRINE
        prog.shrine_reached = True
        controller.zombies = []  # all cleared

        prog.update(0.1, FakePlayer(*config.SHRINE_POS), controller, world)
        self.assertEqual(prog.state, "won")

    # ------------------------------------------------------------------
    def test_notify_sets_message(self):
        prog = Progression()
        prog.notify("Hello world", hold=2.0)
        self.assertEqual(prog.message, "Hello world")
        self.assertAlmostEqual(prog.message_timer, 2.0)
        # The message timer ticks down.
        prog.update(1.0, FakePlayer(1, 1), FakeController(), FakeWorld())
        self.assertAlmostEqual(prog.message_timer, 1.0)
        prog.update(1.0, FakePlayer(1, 1), FakeController(), FakeWorld())
        self.assertEqual(prog.message_timer, 0.0)


if __name__ == "__main__":
    unittest.main()
