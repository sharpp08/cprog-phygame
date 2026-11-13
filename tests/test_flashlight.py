"""Tests for world-aware flashlight attenuation and geometry shadows."""
import unittest
from types import SimpleNamespace

import config
from engine.flashlight import trace_flashlight_beam


class TestFlashlightRayCasting(unittest.TestCase):
    def setUp(self):
        self.world = SimpleNamespace(
            W=24, H=24,
            tiles=[[config.T_GRASS for _ in range(24)] for _ in range(24)],
            obstacles=[],
        )

    def test_clear_beam_reaches_max_range(self):
        rays = trace_flashlight_beam(
            self.world, (4.5, 4.5), (1.0, 0.0),
            max_range=10.0, ray_count=9)
        center = rays[len(rays) // 2]
        self.assertAlmostEqual(center[0], 14.5, delta=0.2)
        self.assertGreater(center[2], 0.0)

    def test_solid_obstacle_casts_a_shadow(self):
        self.world.obstacles = [SimpleNamespace(x=8, y=4, solid=True)]
        rays = trace_flashlight_beam(
            self.world, (4.5, 4.5), (1.0, 0.0),
            max_range=10.0, ray_count=9)
        center = rays[len(rays) // 2]
        self.assertLess(center[0], 8.0)
        self.assertLess(center[0], 14.5)
        self.assertGreater(rays[0][0], center[0])

    def test_non_solid_bush_does_not_block_light(self):
        self.world.obstacles = [SimpleNamespace(x=8, y=4, solid=False)]
        rays = trace_flashlight_beam(
            self.world, (4.5, 4.5), (1.0, 0.0),
            max_range=10.0, ray_count=9)
        self.assertAlmostEqual(rays[4][0], 14.5, delta=0.2)

    def test_water_surface_has_higher_response_than_rock(self):
        water_world = SimpleNamespace(
            W=24, H=24,
            tiles=[[config.T_WATER for _ in range(24)] for _ in range(24)],
            obstacles=[],
        )
        rock_world = SimpleNamespace(
            W=24, H=24,
            tiles=[[config.T_ROCK for _ in range(24)] for _ in range(24)],
            obstacles=[],
        )
        water = trace_flashlight_beam(
            water_world, (4.5, 4.5), (1.0, 0.0),
            max_range=5.0, ray_count=9)[4]
        rock = trace_flashlight_beam(
            rock_world, (4.5, 4.5), (1.0, 0.0),
            max_range=5.0, ray_count=9)[4]
        self.assertGreater(water[2], rock[2])


if __name__ == "__main__":
    unittest.main()
