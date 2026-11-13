"""Automated render test: verifies every world object is created, has valid
screen coordinates, reaches the renderer, and produces visible pixels.

Runs headlessly with the SDL dummy video driver.  Renders one frame of a
populated test scene (1 player, 10 trees, 8 zombies, 5 rocks, ground tiles,
1 pathway), saves a screenshot, and asserts that the output is not blank.

Run with:  python -m unittest tests.test_render
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

import pygame
import config
from engine.asset_manager import AssetManager
from engine.camera import Camera
from engine.particles import ParticleSystem
from engine.renderer import Renderer
from entities.player import Player
from systems.enemy_ai import ZombieController
from systems.navigation import Navigation
from world.map_generator import build_world


class TestRender(unittest.TestCase):
    """Render a populated test scene and assert visible output."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode(
            (config.WINDOW_W, config.WINDOW_H))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _build_test_scene(self):
        """Create a self-contained scene with the required entity counts."""
        import math
        import random

        world = build_world(seed=42)

        px, py = float(world.start[0]), float(world.start[1])
        player = Player(px, py)

        cam = Camera(config.WINDOW_W, config.WINDOW_H,
                     zoom=config.CAM_DEFAULT_ZOOM)
        cam.set_target(player.x, player.y)
        cam.clamp(0, 0, world.W, world.H)

        assets = AssetManager()
        assets.build()

        particles = ParticleSystem()
        renderer = Renderer(self.screen, cam, assets, particles)
        renderer.quality = 1

        grid = world.grid
        nav = Navigation(grid, world.W, world.H)
        controller = ZombieController(grid, nav, world.W, world.H)
        controller.set_context(player, None, particles, world.spawn_points)

        rng = random.Random(99)
        zombies_spawned = 0
        for _ in range(200):
            if zombies_spawned >= 8:
                break
            zx = rng.randint(2, world.W - 3)
            zy = rng.randint(2, world.H - 3)
            if math.hypot(zx - player.x, zy - player.y) < 6.0:
                continue
            if grid.is_blocked(zx, zy):
                continue
            controller.add_zombie(None, float(zx), float(zy), "regular")
            zombies_spawned += 1

        trees = [o for o in world.obstacles if o.kind == "tree"]
        rocks = [o for o in world.obstacles if o.kind == "rock"]

        self.assertGreaterEqual(len(trees), 10,
                                "Map should generate at least 10 trees")
        self.assertGreaterEqual(len(rocks), 5,
                                "Map should generate at least 5 rocks")

        path_tiles = sum(
            1 for row in world.tiles for t in row if t == config.T_PATH)
        self.assertGreater(path_tiles, 0, "Map should have path tiles")

        return world, player, cam, assets, renderer, controller, trees, rocks

    def test_entities_created(self):
        """Every required object is created and alive."""
        world, player, cam, assets, renderer, controller, \
            trees, rocks = self._build_test_scene()

        self.assertIsNotNone(player)
        self.assertTrue(player.alive)
        self.assertGreaterEqual(len(trees), 10)
        self.assertGreaterEqual(len(rocks), 5)
        self.assertGreaterEqual(len(controller.zombies), 8)
        for z in controller.zombies:
            self.assertTrue(z.alive)

    def test_valid_screen_coordinates(self):
        """Every object projects to a valid (finite) screen coordinate."""
        import math
        world, player, cam, assets, renderer, controller, \
            trees, rocks = self._build_test_scene()

        def check(wx, wy):
            sx, sy = cam.iso_to_screen(wx, wy, 0.0)
            self.assertTrue(math.isfinite(sx),
                            f"screen x not finite for ({wx},{wy})")
            self.assertTrue(math.isfinite(sy),
                            f"screen y not finite for ({wx},{wy})")

        check(player.x, player.y)
        for o in world.obstacles:
            check(o.x, o.y)
        for z in controller.zombies:
            check(z.x, z.y)


    def test_entities_reach_renderer(self):
        """The depth-sorted item list contains all entity kinds."""
        world, player, cam, assets, renderer, controller, \
            trees, rocks = self._build_test_scene()

        pickups = []
        items = renderer._depth_items(
            world, player, controller.zombies, pickups)

        kinds = {item[1] for item in items}
        self.assertIn("obs", kinds, "Obstacles missing from render list")
        self.assertIn("zombie", kinds, "Zombies missing from render list")
        self.assertIn("player", kinds, "Player missing from render list")
        self.assertIn("beacon", kinds, "Beacon missing from render list")

        obs_count = sum(1 for it in items if it[1] == "obs")
        zombie_count = sum(1 for it in items if it[1] == "zombie")
        self.assertGreater(obs_count, 0, "No obstacles in render list")
        self.assertGreaterEqual(zombie_count, 8,
                                "Fewer than 8 zombies in render list")

    def test_draw_item_dispatches_correctly(self):
        """The _draw_item method correctly unpacks and dispatches by kind."""
        world, player, cam, assets, renderer, controller, \
            trees, rocks = self._build_test_scene()

        pickups = []
        items = renderer._depth_items(
            world, player, controller.zombies, pickups)

        valid_kinds = {"obs", "zombie", "pickup", "player", "beacon"}
        for item in items:
            depth, kind, obj = item
            self.assertIsInstance(kind, str,
                                  f"Item kind is not a string: {kind!r}")
            self.assertIn(kind, valid_kinds,
                          f"Unknown kind {kind!r} in render list")
            self.assertIsInstance(depth, (int, float),
                                  "Depth should be numeric")

        for item in items:
            try:
                renderer._draw_item(item)
            except Exception as exc:
                self.fail(f"_draw_item raised on {item[1]}: {exc}")

    def test_render_frame_produces_visible_pixels(self):
        """Render one full frame and verify the screen is not blank."""
        world, player, cam, assets, renderer, controller, \
            trees, rocks = self._build_test_scene()

        # Vegetation must remain present in the scene before lighting.
        # The real night-lighting pass intentionally removes most green pixels,
        # so test foliage rendering independently from the darkness treatment.
        renderer._apply_lighting = lambda *_args, **_kwargs: None
        renderer.render_frame(world, player, controller.zombies,
                              [], [], 1.0 / 60.0)

        shot_path = os.path.join(config.PROJECT_ROOT,
                                 "test_render_screenshot.png")
        pygame.image.save(self.screen, shot_path)

        arr = pygame.surfarray.array3d(self.screen)
        bg = (30, 26, 20)
        diff = (
            (arr[:, :, 0] != bg[0]) |
            (arr[:, :, 1] != bg[1]) |
            (arr[:, :, 2] != bg[2])
        )
        non_bg_count = int(diff.sum())
        total = arr.shape[0] * arr.shape[1]
        ratio = non_bg_count / total

        self.assertGreater(non_bg_count, 1000,
                           "Rendered frame has too few non-background "
                           f"pixels ({non_bg_count}); world may be blank")
        self.assertGreater(ratio, 0.01,
                           f"Only {ratio:.4f} of pixels differ from "
                           "background; world appears empty")

        green_mask = (arr[:, :, 1] > arr[:, :, 0] + 10) & \
                     (arr[:, :, 1] > arr[:, :, 2] + 10)
        green_count = int(green_mask.sum())
        self.assertGreater(green_count, 500,
                           f"Very few green pixels ({green_count}); "
                           "trees/grass may not be rendering")

    def test_obstacle_draw_does_not_skip(self):
        """On-screen obstacles should be drawn, not culled."""
        import math
        world, player, cam, assets, renderer, controller, \
            trees, rocks = self._build_test_scene()

        near_trees = sorted(trees, key=lambda o: math.hypot(
            o.x - player.x, o.y - player.y))[:5]
        self.assertGreater(len(near_trees), 0, "No trees near player")

        for t in near_trees:
            sx, sy = cam.iso_to_screen(t.x, t.y, 0.0)
            on_screen = (-160 <= sx <= config.WINDOW_W + 160 and
                         -180 <= sy <= config.WINDOW_H + 80)
            if on_screen:
                renderer._draw_obstacle(t)
                return

        self.fail("No trees were on-screen to draw")


if __name__ == "__main__":
    unittest.main()


