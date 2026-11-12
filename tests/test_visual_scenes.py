"""Capture reproducible, headless visual-review scenes for the renderer.

Run with SDL_VIDEODRIVER=dummy and SDL_AUDIODRIVER=dummy. These images are
actual Pygame render outputs from the game renderer, not static mockups.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

import config
from engine.asset_manager import AssetManager
from engine.camera import Camera
from engine.particles import ParticleSystem
from engine.renderer import Renderer
from entities.player import Player
from entities.zombie import Zombie
from world.map_generator import build_world


class TestVisualScenes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode(
            (config.WINDOW_W, config.WINDOW_H))
        cls.world = build_world(seed=42)
        cls.assets = AssetManager()
        cls.assets.build()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _capture(self, name, player_pos, camera_pos=None, zombies=None):
        px, py = player_pos
        player = Player(float(px), float(py))
        player.aim = (0.85, -0.35)
        cam = Camera(config.WINDOW_W, config.WINDOW_H,
                     zoom=config.CAM_DEFAULT_ZOOM)
        cam.clamp(0, 0, self.world.W, self.world.H)
        cx, cy = camera_pos or player_pos
        cam.set_target(float(cx), float(cy))
        particles = ParticleSystem()
        particles.spawn_fireflies(self.world)
        renderer = Renderer(self.screen, cam, self.assets, particles)
        renderer.quality = 2
        enemies = zombies or []
        renderer.render_frame(self.world, player, enemies, [], [],
                              1.0 / 60.0)
        out_dir = os.path.join(config.PROJECT_ROOT, "graphics_screenshots")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, name + ".png")
        pygame.image.save(self.screen, path)
        self.assertGreater(os.path.getsize(path), 10000)
        return path

    def test_capture_five_visual_review_scenes(self):
        # Broad forest view around the central clearing and its landmarks.
        self._capture("01_forest_environment", (21, 20), (23, 23))

        # Place the player beside a generated tree to inspect scale and
        # contact shadows against surrounding vegetation.
        trees = [o for o in self.world.obstacles if o.kind == "tree"]
        nearest = min(trees, key=lambda o:
                      (o.x - 14) ** 2 + (o.y - 36) ** 2)
        self._capture("02_player_vegetation",
                      (nearest.x + 2.2, nearest.y + 1.4))

        # Three distinct enemy silhouettes in one combat composition.
        encounter_pos = (18.0, 18.0)
        enemies = [
            Zombie(20.0, 18.0, "regular"),
            Zombie(17.0, 20.0, "fast"),
            Zombie(21.0, 21.0, "tank"),
        ]
        for enemy in enemies:
            enemy.anim_state = "walk"
            enemy.frame_index = 1
        self._capture("03_zombie_encounter", encounter_pos,
                      encounter_pos, enemies)

        # Shrine and pond are both visible around the central map landmark.
        self._capture("04_shrine_pond", (25.0, 25.0), (28.0, 28.0))

        # Night lighting and the player's directional flashlight beam.
        self._capture("05_flashlight_night", (20.0, 20.0), (20.0, 20.0),
                      [Zombie(23.0, 19.0, "regular")])

