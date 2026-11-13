"""Headless unit tests for the graphics upgrade: post pipeline, quality
presets, shader management, weather, particles and renderer integration."""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

import config
from graphics import quality_settings
from graphics.post_processing import PostPipeline, ScreenShake
from graphics.shader_manager import ShaderManager, build_manager
from systems.weather import Weather
from engine.particles import ParticleSystem
from systems.save_manager import SaveManager
from entities.player import Player
from entities.weapon import Weapon


class TestQualitySettings(unittest.TestCase):
    def test_four_quality_levels(self):
        self.assertEqual(len(config.QUALITY), 4)
        self.assertEqual(list(config.QUALITY),
                         ["low", "medium", "high", "ultra"])

    def test_presets_are_monotonic(self):
        p = [quality_settings.particle_scale(q) for q in range(4)]
        self.assertTrue(p[0] <= p[1] <= p[2] <= p[3])
        r = [quality_settings.fx_downscale(q) for q in range(4)]
        # effect resolution scale-down shrinks as quality rises
        self.assertTrue(r[0] >= r[1] >= r[2] >= r[3])

    def test_flags_per_preset(self):
        low = quality_settings.specs_for(0)
        ultra = quality_settings.specs_for(3)
        self.assertFalse(low["post_fx"])
        self.assertFalse(low["bloom"])
        self.assertTrue(ultra["post_fx"])
        self.assertGreater(ultra["bloom"], 0.0)
        self.assertGreater(ultra["chroma"], 0.0)
        self.assertGreater(ultra["distort"], 0.0)
        # out-of-range quality indexes never raise
        self.assertEqual(quality_settings.specs_for(9),
                         quality_settings.specs_for(3))
        self.assertEqual(quality_settings.specs_for(-5),
                         quality_settings.specs_for(0))


class TestPostPipeline(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((320, 180))

    def tearDown(self):
        pygame.quit()

    def test_disabled_pipeline_copies_scene(self):
        pp = PostPipeline(320, 180, quality=0, post_fx=False)
        self.assertFalse(pp.enabled)
        pp.scene.fill((90, 100, 110))
        player = Player(1.0, 1.0)
        pp.present(self.screen, player)
        self.assertEqual(tuple(self.screen.get_at((5, 5)))[:3],
                         (90, 100, 110))

    def test_present_does_not_crash_when_enabled(self):
        pp = PostPipeline(320, 180, quality=3)
        self.assertTrue(pp.enabled)
        pp.scene.fill((70, 80, 90))
        player = Player(1.0, 1.0)
        for _ in range(5):
            pp.update(1 / 60.0, tension=0.5)
            pp.present(self.screen, player, low_hp=True, dt=1 / 60.0,
                       tension=0.5)
        px = self.screen.get_at((160, 90))
        self.assertTrue(all(0 <= c <= 255 for c in px[:3]))

    def test_damage_flash_modifies_image(self):
        pp = PostPipeline(320, 180, quality=2)
        pp.scene.fill((40, 40, 40))
        player = Player(1.0, 1.0)
        before = pp.scene.copy()
        pp.present(self.screen, player)
        pp.on_damage(1.0)
        pp.scene.blit(before, (0, 0))
        pp.present(self.screen, player)
        # a red flash must have changed the frame
        diff = abs(int(self.screen.get_at((160, 90))[0]) -
                   int(before.get_at((160, 90))[0]))
        self.assertGreater(diff, 5)

    def test_low_health_heartbeat_pulse(self):
        pp = PostPipeline(320, 180, quality=2)
        pp.set_low_health(True, dt=0.5)
        self.assertGreater(pp._vignette_pulse, 0.0)
        pp.set_low_health(False, dt=1.0)
        self.assertEqual(pp._vignette_pulse, 0.0)

    def test_resize_rebuilds_buffers(self):
        pp = PostPipeline(320, 180, quality=1)
        pp.resize(480, 270)
        self.assertEqual(pp.scene.get_size(), (480, 270))
        self.assertGreater(pp._fxw, 0)
        self.assertGreater(pp._fxh, 0)

    def test_post_fx_override(self):
        pp = PostPipeline(320, 180, quality=3, post_fx=False)
        self.assertFalse(pp.enabled)
        pp.resize(320, 180, quality=3, enabled=True)
        self.assertTrue(pp.enabled)
        # back to preset-driven (None)
        pp.resize(320, 180, quality=0, enabled=None)
        self.assertFalse(pp.enabled)  # low preset disables post fx


class TestScreenShake(unittest.TestCase):
    def test_shake_decays_to_zero(self):
        s = ScreenShake()
        s.add(6.0, 0.5)
        for _ in range(120):
            s.update(1.0 / 60.0)
        self.assertEqual(s.offset(), (0, 0))

    def test_shake_is_active_immediately(self):
        s = ScreenShake()
        s.add(8.0, 1.0)
        s.update(1.0 / 60.0)
        dx, dy = s.offset()
        self.assertGreaterEqual(abs(dx) + abs(dy), 1)


class TestShaderManager(unittest.TestCase):
    def test_all_shader_sources_load(self):
        mgr = ShaderManager()
        expected = {"color_grading", "vignette", "film_grain",
                    "chromatic_aberration", "bloom", "distortion",
                    "fog", "flashlight"}
        self.assertTrue(expected.issubset(mgr.programs.keys()))
        for name, prog in mgr.programs.items():
            self.assertIn("gl_FragColor", prog.source,
                          f"{name} has no output statement")

    def test_compile_is_never_fatal(self):
        mgr = build_manager()
        # must return without raising, whatever the GPU state is
        self.assertIsInstance(mgr.gl_available, bool)
        for err in mgr.errors:
            self.assertIsInstance(err, str)

    def test_vertex_source_present(self):
        mgr = ShaderManager()
        self.assertIn("gl_Position", mgr.vertex_source)


class TestWeather(unittest.TestCase):
    def test_lightning_only_in_heavy_rain(self):
        w = Weather(seed=7)
        w.target_state = "heavy_rain"
        w.state = "heavy_rain"
        w._lightning_timer = 0.0
        w.lightning = 0.0
        events = [w.update(0.1) for _ in range(3)]
        self.assertEqual(events[0], "lightning")
        self.assertGreater(w.lightning, 0.0)

    def test_no_lightning_when_clear(self):
        w = Weather(seed=3)
        w.state = "clear"
        self.assertIsNone(w.update(0.5))
        self.assertEqual(w.rain_amount, 0.0)

    def test_rain_amount_eases_toward_target(self):
        w = Weather(seed=11)
        w.target_state = "heavy_rain"
        w._next_transition = 10_000.0  # no re-roll during the test
        for _ in range(4000):
            w.update(1.0 / 30.0)
        self.assertGreater(w.rain_amount, 0.95)
        self.assertEqual(w.rain_intensity(), 2)



class TestAmbientParticles(unittest.TestCase):
    def test_ambient_spawner_respects_pool(self):
        ps = ParticleSystem()
        ps.set_max(120)
        world = type("W", (), {"shrine": (10, 10), "W": 20, "H": 20})()
        ps.spawn_ambient(world, scale=1.0)
        kinds = {p.kind for p in ps.particles}
        self.assertIn("leaf", kinds)
        self.assertIn("dust", kinds)
        self.assertIn("ember", kinds)
        self.assertLessEqual(len(ps.particles), ps._max)

    def test_wind_drifts_leaves(self):
        ps = ParticleSystem()
        ps.set_wind(0.9)
        world = type("W", (), {"shrine": (5, 5), "W": 20, "H": 20})()
        ps.spawn_ambient(world)
        leaves = [p for p in ps.particles if p.kind == "leaf"]
        self.assertTrue(leaves)
        x0 = sum(p.x for p in leaves) / len(leaves)
        for _ in range(10):
            ps.update(1.0, world, wind=0.9)
        alive = [p for p in ps.particles if p.kind == "leaf"]
        if alive:
            x1 = sum(p.x for p in alive) / len(alive)
            self.assertGreater(x1, x0 - 0.5)


class TestRendererGraphicsIntegration(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode(
            (config.WINDOW_W, config.WINDOW_H))
        from engine.asset_manager import AssetManager
        from engine.camera import Camera
        from engine.renderer import Renderer
        from world.map_generator import build_world
        self.world = build_world(seed=42)
        self.player = Player(21.0, 20.0)
        self.player.aim = (0.8, -0.3)
        cam = Camera(config.WINDOW_W, config.WINDOW_H,
                     zoom=config.CAM_DEFAULT_ZOOM)
        cam.set_target(self.player.x, self.player.y)
        cam.clamp(0, 0, self.world.W, self.world.H)
        assets = AssetManager()
        assets.build()
        self.renderer = Renderer(self.screen, cam, assets,
                                 ParticleSystem())

    def tearDown(self):
        pygame.quit()

    def test_renderer_owns_graphics_subsystems(self):
        r = self.renderer
        self.assertTrue(hasattr(r, "post"))
        self.assertTrue(hasattr(r, "shake"))
        self.assertTrue(hasattr(r, "weather"))
        self.assertIsInstance(r.post, PostPipeline)

    def test_quality_switching_does_not_crash(self):
        for q in range(4):
            self.renderer._apply_quality(q)
            self.renderer.render_frame(self.world, self.player,
                                       [], [], [], 1 / 60.0)
        self.assertEqual(self.renderer.quality, 3)

    def test_post_fx_toggle(self):
        self.renderer.set_post_fx(False)
        self.assertFalse(self.renderer.post.enabled)
        self.renderer.set_post_fx(True)
        self.assertTrue(self.renderer.post.enabled)
        self.renderer.set_post_fx(None)
        # back to preset-driven (quality 1 -> enabled by default)
        self.assertEqual(self.renderer.post.enabled,
                         bool(quality_settings.specs_for(1)["post_fx"]))

    def test_damage_triggers_flash_and_shake(self):
        self.renderer._last_hp = 100.0
        self.player.hp = 70.0
        self.renderer.render_frame(self.world, self.player,
                                   [], [], [], 1 / 60.0)
        self.assertGreater(self.renderer.post._flash_red, 0.0)

    def test_weather_tick_and_lightning_flash(self):
        w = self.renderer.weather
        w.target_state = "heavy_rain"
        w.state = "heavy_rain"
        w._lightning_timer = 0.0
        ev = self.renderer.tick_weather(0.1)
        self.assertEqual(ev, "lightning")
        self.assertGreater(self.renderer.post._flash_white, 0.0)

    def test_rain_rendering_does_not_crash(self):
        self.renderer.weather.rain_amount = 1.0
        self.renderer._apply_quality(1)
        self.renderer.render_frame(self.world, self.player,
                                   [], [], [], 1 / 60.0)
        self.assertGreater(len(self.renderer._rain), 0)


class TestSettingsPersistence(unittest.TestCase):
    def test_graphics_settings_roundtrip(self):
        import tempfile
        sm = SaveManager(save_dir=tempfile.mkdtemp())
        player = Player(1.0, 1.0)
        player.weapons = [Weapon("pistol")]
        progression = type("P", (), {
            "phase": "explore", "state": "playing", "score": 5,
            "kills": 1, "time": 3.0, "wave": 0,
            "shrine_reached": False})()
        settings = {"master": 0.5, "music": 0.4, "sfx": 0.7,
                    "resolution": 0, "fullscreen": False, "quality": 3,
                    "zoom": 1.2, "post_fx": None}
        self.assertTrue(sm.save(player, progression, settings))
        data = sm.load()
        self.assertIsNotNone(data)
        self.assertEqual(data["settings"]["quality"], 3)
        self.assertIsNone(data["settings"]["post_fx"])
        os.remove(sm.path)


if __name__ == "__main__":
    unittest.main()

