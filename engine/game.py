"""The game: owns state, the loop, menus and ties every system together."""
from __future__ import annotations

from typing import Callable, Optional
import json
import os

import pygame

import config
from engine.asset_manager import AssetManager
from engine.audio_manager import AudioManager
from engine.camera import Camera
from engine.input_manager import InputManager
from engine.particles import ParticleSystem
from engine.renderer import Renderer
from entities.player import Player
from entities.weapon import Weapon
from systems.combat import CombatSystem
from systems.inventory import apply_pickup
from systems.progression import Progression
from systems.horror_director import HorrorDirector
from systems.horde_director import HordeDirector
from systems.storytelling import StorySystem
from systems.survival import SurvivalSystem
from systems.save_manager import SaveManager
from graphics.shader_manager import build_manager
from ui.game_over import GameOver
from ui.hud import HUD
from ui.main_menu import MainMenu
from ui.pause_menu import PauseMenu
from ui.inventory_menu import InventoryMenu
from ui.settings_menu import SettingsMenu
from ui.widgets import FontSet
from ui.loading_screen import LoadingScreen


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


class Game:
    def __init__(self, window) -> None:
        self.window = window
        self.screen = window.screen
        self.settings = {
            "master": config.MASTER_VOL, "music": config.MUSIC_VOL,
            "sfx": config.SFX_VOL, "resolution": config.DEFAULT_RESOLUTION,
            "fullscreen": config.FULLSCREEN, "quality": 2,
            "zoom": config.DEFAULT_ZOOM, "post_fx": False,
        }
        self._settings_path = os.path.join(config.SAVE_DIR, "settings.json")
        self._load_user_settings()
        self.audio = AudioManager()
        self.assets = AssetManager()
        self.particles = ParticleSystem()
        # Pre-compile the GLSL post-processing shaders at startup so no
        # shader work ever happens inside the gameplay loop.  The live
        # context is only used when ModernGL works on this machine; the
        # NumPy post pipeline stays the guaranteed fallback.
        self.shaders = None
        self.input = InputManager()
        self.save_manager = SaveManager()
        self.fonts = FontSet()

        self.state = "menu"
        self._settings_return = "menu"
        self.running = True
        self.clock = pygame.time.Clock()
        self.dt = 1.0 / config.TARGET_FPS
        self._fixed_dt = 1.0 / config.TARGET_FPS
        self._sim_accumulator = 0.0
        self._menu_time = 0.0

        # menus
        self.main_menu = MainMenu(*self.screen.get_size(),
                                  self.save_manager.has_save())
        self.loading_screen = LoadingScreen(config.WINDOW_W, config.WINDOW_H)
        self.pause_menu: Optional[PauseMenu] = None
        self.inventory_menu: Optional[InventoryMenu] = None
        self.settings_menu: Optional[SettingsMenu] = None
        self.game_over: Optional[GameOver] = None
        self.hud: Optional[HUD] = None

        # per-game objects (None until a game starts)
        self.wm = None
        self.player: Optional[Player] = None
        self.cam: Optional[Camera] = None
        self.renderer: Optional[Renderer] = None
        self.combat: Optional[CombatSystem] = None
        self.progression: Optional[Progression] = None
        self.survival: Optional[SurvivalSystem] = None
        self.story: Optional[StorySystem] = None
        self.horror: Optional[HorrorDirector] = None
        self.hordes: Optional[HordeDirector] = None
        self._prev_hp = 0.0
        self._heartbeat_timer = 0.0
        self._breath_timer = 0.0
        self._last_nearby_threats = 0
        self._last = pygame.time.get_ticks()

    # ------------------------------------------------------------------
    def _load_user_settings(self) -> None:
        """Load validated user preferences independently of the game save."""
        try:
            with open(self._settings_path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
            if not isinstance(saved, dict):
                return
            for key in ("master", "music", "sfx"):
                if key in saved:
                    self.settings[key] = max(0.0, min(1.0, float(saved[key])))
            if "resolution" in saved:
                self.settings["resolution"] = max(0, min(
                    len(config.RESOLUTIONS) - 1, int(saved["resolution"])))
            if "fullscreen" in saved:
                self.settings["fullscreen"] = bool(saved["fullscreen"])
            if "quality" in saved:
                self.settings["quality"] = max(0, min(3, int(saved["quality"])))
            if "zoom" in saved:
                self.settings["zoom"] = max(config.ZOOM_MIN, min(
                    config.ZOOM_MAX, float(saved["zoom"])))
            if saved.get("post_fx") in (None, True, False):
                self.settings["post_fx"] = saved.get("post_fx")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def _save_user_settings(self) -> None:
        """Persist preferences even when the player has no active save."""
        try:
            os.makedirs(os.path.dirname(self._settings_path), exist_ok=True)
            with open(self._settings_path, "w", encoding="utf-8") as handle:
                json.dump(self.settings, handle, indent=2)
        except OSError as exc:
            print(f"[Settings] Could not save preferences: {exc}")

    def _init_audio(self) -> None:
        self.audio.init()
        self.audio.set_volumes(self.settings["master"], self.settings["music"],
                               self.settings["sfx"])

    # ------------------------------------------------------------------
    def apply_settings(self, apply_window: bool = True) -> None:
        self.assets.set_quality(int(self.settings["quality"]))
        if self.cam is not None:
            self.cam.set_zoom(float(self.settings["zoom"]))
        if self.renderer is not None:
            self.renderer._apply_quality(int(self.settings["quality"]))
            self.renderer.set_post_fx(self.settings.get("post_fx"))
        if apply_window:
            self.window.set_mode(self.settings["resolution"],
                                self.settings["fullscreen"])
            self.screen = self.window.screen
            # Asset generation is deferred until the startup loading scene is
            # already visible; a display change does not require rebuilding it.
            self._rebind_game()
            w, h = self.screen.get_size()
            self.loading_screen = LoadingScreen(w, h)
            if self.renderer is not None:
                self.renderer.set_post_fx(self.settings.get("post_fx"))
            self.main_menu = MainMenu(w, h, self.save_manager.has_save())
            if self.pause_menu is not None:
                self.pause_menu = PauseMenu(w, h)
            if self.game_over is not None:
                self.game_over = GameOver(w, h)
        self.audio.set_volumes(self.settings["master"],
                              self.settings["music"],
                              self.settings["sfx"])
        self._save_user_settings()

    def _rebind_game(self) -> None:
        w, h = self.screen.get_size()
        if self.cam is not None:
            self.cam.set_size(w, h)
        if self.renderer is not None:
            self.renderer.screen = self.screen
            self.renderer.W, self.renderer.H = w, h
            self.renderer._prep_fog()
        self.hud = HUD(w, h)

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------
    def _pump_transition_events(self) -> bool:
        """Handle quit/alt-f4 while a transition holds the loop; True=alive."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return False
            if event.type == pygame.KEYDOWN and                     event.key == pygame.K_F4 and                     (pygame.key.get_mods() & pygame.KMOD_ALT):
                self.running = False
                return False
        return True

    def _crossfade(self, render_new: Callable[[], None],
                   duration: float = 0.7) -> None:
        """Blend smoothly from the current frame to render_new()'s frame.

        Eliminates black-screen flashes and abrupt scene changes between
        the menu, loading screen, gameplay and settings.
        """
        if not self.running:
            return
        prev = self.screen.copy()
        render_new()
        nxt = self.screen.copy()
        clock = pygame.time.Clock()
        started = pygame.time.get_ticks()
        ms = max(1, int(duration * 1000))
        while self.running:
            if not self._pump_transition_events():
                return
            k = min(1.0, (pygame.time.get_ticks() - started) / ms)
            e = _ease(k)
            self.screen.blit(prev, (0, 0))
            nxt.set_alpha(int(255 * e))
            self.screen.blit(nxt, (0, 0))
            nxt.set_alpha(255)
            pygame.display.flip()
            if k >= 1.0:
                break
            clock.tick(60)
        self.screen.blit(nxt, (0, 0))
        pygame.display.flip()

    def _present(self) -> None:
        """Immediately draw and show the current state (post mode change)."""
        self._render()
        pygame.display.flip()

    def _draw_menu_scene(self) -> None:
        self.main_menu.draw(self.screen, self.fonts,
                            self.dt if self.dt > 0 else 1.0 / 60.0)

    # ------------------------------------------------------------------
    def start_new(self) -> None:
        # Fade out of whatever screen we are on into the loading interstitial
        # so world generation never starts from a black or stale frame.
        self._crossfade(lambda: self.loading_screen.draw(
            self.screen, 0.0, "GENERATING A NEW WORLD"), duration=0.45)
        self._show_loading_screen("GENERATING A NEW WORLD")
        self._init_world()
        self.player = Player(float(self.wm.world.start[0]),
                             float(self.wm.world.start[1]))
        self.wm.setup(self.player, self.audio, self.particles)
        self.combat = CombatSystem(self.wm.grid)
        self.progression = Progression()
        self.survival = SurvivalSystem()
        self.player.flashlight_on = self.survival.flashlight_on
        self.story = StorySystem(self.wm.world)
        self.horror = HorrorDirector()
        self.hordes = HordeDirector()
        self.cam = Camera(*self.screen.get_size(),
                          zoom=self.settings["zoom"])
        self.cam.set_target(self.player.x, self.player.y)
        self.cam.clamp(0, 0, self.wm.world.W, self.wm.world.H)
        self.renderer = Renderer(self.screen, self.cam, self.assets,
                                 self.particles, self.shaders)
        self.renderer._apply_quality(int(self.settings["quality"]))
        self.renderer.set_post_fx(self.settings.get("post_fx"))
        self.renderer.weather.set_audio(self.audio)
        w, h = self.screen.get_size()
        self.renderer.W, self.renderer.H = w, h
        self.renderer._prep_fog()
        self.hud = HUD(w, h)
        self._prev_hp = self.player.hp
        self._last_nearby_threats = 0
        self.state = "playing"
        self.save_manager.delete()
        self.audio.play_music("ambient")
        self.progression.notify("Find the ancient shrine. Follow the path.")
        # Ease into the first gameplay frame instead of popping.
        self._present()
        self._crossfade(self._render, duration=0.6)
        self._print_world_diagnostics()

    def _show_loading_screen(self, message: str) -> None:
        """Present a short animated forest interstitial before world setup."""
        if not self.running:
            return
        clock = pygame.time.Clock()
        started = pygame.time.get_ticks()
        duration = 1050
        while self.running and pygame.time.get_ticks() - started < duration:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F4 and (pygame.key.get_mods() & pygame.KMOD_ALT):
                    self.running = False
                    return
            elapsed = (pygame.time.get_ticks() - started) / 1000.0
            self.loading_screen.draw(self.screen, elapsed, message)
            pygame.display.flip()
            clock.tick(45)

    def _init_world(self) -> None:
        from systems.world_manager import WorldManager
        self.wm = WorldManager()
        self.particles.clear()

    # ------------------------------------------------------------------
    def _print_world_diagnostics(self) -> None:
        """Print a one-time diagnostic summary of entity creation and
        registration to confirm the world is populated at startup."""
        w = self.wm.world
        trees = [o for o in w.obstacles if o.kind == "tree"]
        rocks = [o for o in w.obstacles if o.kind == "rock"]
        bushes = [o for o in w.obstacles if o.kind == "bush"]
        zombies = self.wm.controller.zombies
        psx, psy = self.cam.iso_to_screen(self.player.x, self.player.y, 0.0)
        in_view = 0
        for o in w.obstacles:
            ox, oy = self.cam.iso_to_screen(o.x, o.y, 0.0)
            if -160 <= ox <= self.cam.sw + 160 and \
                    -180 <= oy <= self.cam.sh + 80:
                in_view += 1
        print("=" * 60)
        print("WORLD INITIALIZED: YES")
        print(f"PLAYER CREATED: YES  pos=({self.player.x:.1f}, "
              f"{self.player.y:.1f}) hp={self.player.hp}")
        print(f"PLAYER REGISTERED: YES  screen=({psx:.0f}, {psy:.0f})")
        print(f"TREES GENERATED: {len(trees)}")
        print(f"TREES REGISTERED: {len(trees)} (in world.obstacles)")
        print(f"ROCKS GENERATED: {len(rocks)}")
        print(f"BUSHES GENERATED: {len(bushes)}")
        print(f"ENEMIES SPAWNED: {len(zombies)}")
        print(f"ENEMIES REGISTERED: {len(zombies)} (in controller.zombies)")
        print(f"RENDERABLE ENTITIES (obstacles): {len(w.obstacles)}")
        print(f"VISIBLE ENTITIES (obstacles in view): {in_view}")
        print(f"PICKUPS: {len(self.wm.pickups)}")
        print(f"MAP: {w.W}x{w.H}  CAMERA: ({self.cam.fx:.1f}, "
              f"{self.cam.fy:.1f}) zoom={self.cam.zoom:.2f}")
        print("=" * 60)

    # ------------------------------------------------------------------
    def load_game(self) -> bool:
        self._crossfade(lambda: self.loading_screen.draw(
            self.screen, 0.0, "RESTORING YOUR LAST JOURNEY"), duration=0.45)
        self._show_loading_screen("RESTORING YOUR LAST JOURNEY")
        data = self.save_manager.load()
        if data is None:
            self.start_new()
            return False
        self._init_world()
        pd = data["player"]
        saved_world = data.get("world", {})
        if not isinstance(saved_world, dict):
            saved_world = {}
        saved_w = max(2, int(saved_world.get("width", 48)))
        saved_h = max(2, int(saved_world.get("height", 48)))
        px = float(pd["x"]) * (self.wm.world.W - 1) / (saved_w - 1)
        py = float(pd["y"]) * (self.wm.world.H - 1) / (saved_h - 1)
        # Old 48x48 saves are proportionally migrated to the expanded forest.
        if self.wm.grid.is_blocked(int(round(px)), int(round(py))):
            clear_x, clear_y = self.wm.grid.find_clear_tile((px, py))
            px, py = clear_x + 0.5, clear_y + 0.5
        weapons = [Weapon.from_dict(w) for w in pd["weapons"]]
        self.player = Player(px, py, weapons=weapons)
        self.player.current = pd.get("current", 0)
        self.player.hp = pd.get("hp", config.PLAYER_MAX_HP)
        pg = data["progression"]
        self.wm.setup(self.player, self.audio, self.particles)
        self.combat = CombatSystem(self.wm.grid)
        self.progression = Progression()
        self.survival = SurvivalSystem()
        self.story = StorySystem(self.wm.world)
        self.horror = HorrorDirector()
        self.hordes = HordeDirector()
        self.story.discovered.update(pg.get("clues", []))
        sd = data.get("survival", {})
        self.survival.stamina = float(sd.get("stamina", 100.0))
        self.survival.scrap = int(sd.get("scrap", 0))
        self.survival.flashlight_battery = float(sd.get("flashlight_battery", 100.0))
        self.survival.battery_cells = int(sd.get("battery_cells", 2))
        self.survival.flashlight_on = bool(sd.get("flashlight_on", True))
        self.survival.medkits = max(0, min(9, int(sd.get("medkits", 1))))
        self.survival.grenades = max(0, min(9, int(sd.get("grenades", 2))))
        self.player.flashlight_on = self.survival.flashlight_on
        self.progression.phase = pg.get("phase", "explore")
        self.progression.state = "playing"
        self.progression.score = pg.get("score", 0)
        self.progression.kills = pg.get("kills", 0)
        self.progression.time = pg.get("time", 0.0)
        self.progression.wave = pg.get("wave", 0)
        self.progression.shrine_reached = pg.get("shrine_reached", False)
        if self.progression.phase == "shrine":
            self.progression.objective = "Survive the final waves at the shrine"
        self.cam = Camera(*self.screen.get_size(),
                          zoom=self.settings["zoom"])
        self.cam.set_target(self.player.x, self.player.y)
        self.cam.clamp(0, 0, self.wm.world.W, self.wm.world.H)
        self.renderer = Renderer(self.screen, self.cam, self.assets,
                                 self.particles, self.shaders)
        self.renderer._apply_quality(int(self.settings["quality"]))
        self.renderer.set_post_fx(self.settings.get("post_fx"))
        self.renderer.weather.set_audio(self.audio)
        w, h = self.screen.get_size()
        self.renderer.W, self.renderer.H = w, h
        self.renderer._prep_fog()
        self.hud = HUD(w, h)
        self._prev_hp = self.player.hp
        self._last_nearby_threats = 0
        self.state = "playing"
        self.audio.play_music("ambient")
        # restore persisted graphics / audio settings from the save
        self.settings.update({k: v for k, v in
                              data.get("settings", {}).items()
                              if k in self.settings})
        self._present()
        self._crossfade(self._render, duration=0.6)
        return True

    # ------------------------------------------------------------------
    def _enter_gameover(self) -> None:
        self.state = "gameover"
        self.game_over = GameOver(*self.screen.get_size())
        if self.progression.state == "won" and self.story is not None:
            self.game_over.ending_title, self.game_over.ending_subtitle = self.story.ending()
        self.audio.stop_music()
        # A lost run must not be offered as a resumable Continue save with
        # zero HP. Progress is saved only when the player deliberately
        # returns to the main menu while still alive.
        self.save_manager.delete()
        # Present the game-over screen through the shared renderer first so
        # the crossfade starts from the live world frame, not a stale menu.
        self._present()
        self._crossfade(self._render, duration=0.55)

    # ------------------------------------------------------------------
    def _transition_loading_to_menu(self) -> None:
        """Crossfade the animated forest interstitial into the finished menu."""
        if not self.running:
            return
        menu_frame = pygame.Surface(self.screen.get_size()).convert()
        self._draw_menu_scene()
        menu_frame.blit(self.screen, (0, 0))
        clock = pygame.time.Clock()
        started = pygame.time.get_ticks()
        duration = 1400
        while self.running:
            if not self._pump_transition_events():
                return
            elapsed = (pygame.time.get_ticks() - started) / 1000.0
            t = min(1.0, elapsed / (duration / 1000.0))
            eased = _ease(t)
            self.loading_screen.draw(
                self.screen, elapsed, "ENTERING THE FOREST")
            menu_frame.set_alpha(int(255 * eased))
            self.screen.blit(menu_frame, (0, 0))
            pygame.display.flip()
            if t >= 1.0:
                break
            clock.tick(45)
        menu_frame.set_alpha(255)
        self.screen.blit(menu_frame, (0, 0))
        pygame.display.flip()

    def run(self) -> None:
        self._init_audio()
        self.loading_screen = LoadingScreen(*self.screen.get_size())
        self._show_loading_screen("INITIALIZING THE FOREST")
        self.shaders = build_manager(live=True)
        self.assets.build()
        self.audio.play_music("menu")
        self._transition_loading_to_menu()
        while self.running:
            self._frame()
        self._save_user_settings()
        if self.shaders is not None:
            self.shaders.release()
        pygame.quit()

    # ------------------------------------------------------------------
    def _frame(self) -> None:
        # Fixed-step simulation keeps movement, collision and animation stable.
        frame_dt = min(max((pygame.time.get_ticks() - self._last) / 1000.0,
                           0.0), 0.1)
        self._last = pygame.time.get_ticks()
        for event in pygame.event.get():
            self._on_event(event)
        self._sim_accumulator = min(
            self._sim_accumulator + frame_dt, self._fixed_dt * 8.0)
        steps = 0
        while self._sim_accumulator >= self._fixed_dt and steps < 8:
            self.dt = self._fixed_dt
            self._update(self._fixed_dt)
            self._sim_accumulator -= self._fixed_dt
            steps += 1
        if self.state == "menu":
            # Menu animations run on real frame time, not the fixed step.
            self.dt = max(frame_dt, 1e-4)
        self._render()
        self.clock.tick(config.MAX_RENDER_FPS)
        pygame.display.flip()
        self.input.end_frame()

    # ------------------------------------------------------------------
    def _on_event(self, event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
            if self.renderer is not None:
                self.renderer.show_debug = not self.renderer.show_debug
            return
        if self.state == "menu":
            self._handle_menu_result(self.main_menu.handle(event,
                                                           self.audio))
        elif self.state == "playing":
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_i, pygame.K_TAB):
                self._open_inventory()
                return
            self.input.process(event)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                if self.survival is not None:
                    enabled = self.survival.toggle_flashlight()
                    self.player.flashlight_on = enabled
                    self.progression.notify(
                        "Flashlight ON" if enabled else "Flashlight OFF", 1.5)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                if self.story is not None:
                    clue = self.story.interact(self.player.x, self.player.y)
                    if clue:
                        self.progression.notify(clue["text"], 6.0)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_b:
                if self.survival and self.survival.replace_battery():
                    self.player.flashlight_on = self.survival.flashlight_on
                    self.progression.notify("Fresh flashlight cell installed", 2.0)
                    self.audio.play("battery_swap")
                elif self.survival:
                    self.progression.notify("No spare cell or battery is already full", 2.0)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                if self.survival and self.survival.craft_medkit(self.player):
                    self.progression.notify("Medkit crafted and stored", 2.5)
                    self.audio.play("pickup")
                elif self.survival:
                    self.progression.notify("Need 3 scrap and missing health to craft", 2.0)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                if self.combat is not None:
                    self.combat.request_melee(self.player)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_g:
                if self.survival and self.survival.grenades > 0 and self.combat:
                    if self.combat.throw_grenade(self.player, self.player.aim):
                        self.survival.grenades -= 1
                        self.wm.controller.emit_noise(self.player.x, self.player.y, 15.0, 1.0)
                elif self.survival:
                    self.progression.notify("No grenades available", 1.5)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
                if self.survival and self.survival.use_medkit(self.player):
                    self.progression.notify("Medkit used (+40 HP)", 1.8)
                    self.audio.play("medkit_use")
                elif self.survival:
                    self.progression.notify("No medkit or health is already full", 1.8)
            if InputManager.pause_pressed():
                self._open_pause()
        elif self.state == "inventory":
            if self.inventory_menu is not None:
                result = self.inventory_menu.handle(
                    event, self.player, self.survival, self.story, self.audio)
                if result == "close":
                    self.inventory_menu = None
                    self.state = "playing"
        elif self.state == "paused":
            self._handle_pause_result(self.pause_menu.handle(event,
                                                             self.audio))
        elif self.state == "settings":
            if self.settings_menu is not None:
                res = self.settings_menu.handle(event)
                if res == "back":
                    self.apply_settings(True)
                    self.state = self._settings_return
                    self.settings_menu = None
                    # Re-present immediately so a resolution/fullscreen
                    # change never leaves a black or stale frame visible.
                    self._present()
        elif self.state == "gameover":
            if self.game_over:
                res = self.game_over.handle(event, self.audio)
                if res == "restart":
                    self.start_new()
                elif res == "main_menu":
                    self._to_main_menu()

    # ------------------------------------------------------------------
    def _handle_menu_result(self, res) -> None:
        if res == "start":
            self.start_new()
        elif res == "continue":
            self.load_game()
        elif res == "settings":
            self._open_settings("menu")
        elif res == "exit":
            self.running = False

    def _open_settings(self, return_state: str) -> None:
        self._settings_return = return_state
        self.settings_menu = SettingsMenu(
            *self.screen.get_size(), self.settings, self.audio,
            camera=self.cam, on_apply=lambda: self.apply_settings(False))
        self.settings_menu.set_back_target(return_state)
        self.state = "settings"
        # Fade into the settings page over the preserved background.
        self._crossfade(self._render, duration=0.35)

    def _open_inventory(self) -> None:
        self.inventory_menu = InventoryMenu(*self.screen.get_size())
        self.state = "inventory"
        self.audio.play("inventory_open")
        self._crossfade(self._render, duration=0.18)

    def _open_pause(self) -> None:
        self.pause_menu = PauseMenu(*self.screen.get_size())
        self.state = "paused"
        self._crossfade(self._render, duration=0.3)

    def _handle_pause_result(self, res) -> None:
        if res == "resume":
            self.state = "playing"
            self._present()
            self._crossfade(self._render, duration=0.3)
        elif res == "settings":
            self._open_settings("paused")
        elif res == "restart":
            self.start_new()
        elif res == "main_menu":
            self._to_main_menu()
        elif res == "exit":
            self.running = False

    def _to_main_menu(self) -> None:
        if self.player is not None and self.progression is not None \
                and self.progression.state == "playing":
            self.save_manager.save(self.player, self.progression,
                                   self.settings, self.story, self.survival)
        self.audio.stop_rain()
        self.state = "menu"
        self.settings_menu = None
        self.pause_menu = None
        self.main_menu = MainMenu(*self.screen.get_size(),
                                  self.save_manager.has_save())
        self.audio.play_music("menu")
        # Crossfade from the live world/settings frame back to the menu.
        self._crossfade(self._draw_menu_scene, duration=0.8)

    # ------------------------------------------------------------------
    def _update(self, dt: float) -> None:
        if self.state == "playing":
            self._update_playing(dt)

    def _update_playing(self, dt: float) -> None:
        player = self.player
        cam = self.cam
        # aim + facing
        aim = InputManager.compute_aim(cam, player)
        player.set_aim(aim[0], aim[1])
        # movement
        mv = InputManager.move_vector()
        requested_run = InputManager.running() and (mv[0] != 0.0 or mv[1] != 0.0)
        keys = pygame.key.get_pressed()
        crouching = bool(keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL])
        player.crouching = crouching
        sprinting = requested_run and not crouching
        can_run = self.survival.update(dt, sprinting) if self.survival else True
        if self.survival is not None:
            player.flashlight_on = self.survival.flashlight_on
        player.apply_movement(mv, sprinting and can_run, dt, self.wm.grid,
                              speed_scale=0.52 if crouching else 1.0)
        player.update(dt)
        player.z = self.wm.world.height_at(player.x, player.y) * config.TERRAIN_HEIGHT_SCALE
        if player.footstep_sound:
            self.audio.play("footstep_run" if player.running else ("footstep_crouch" if crouching else "footstep_walk"))
            if self.wm.controller:
                self.wm.controller.emit_noise(
                    player.x, player.y,
                    11.0 if player.running else (2.4 if crouching else 5.0),
                    1.1 if player.running else 0.45)
            player.footstep_sound = False
        # weapon switching 1/2/3
        k = pygame.key.get_pressed()
        for idx, key in ((0, pygame.K_1), (1, pygame.K_2),
                         (2, pygame.K_3)):
            if k[key] and idx < len(player.weapons) and \
                    idx != player.current:
                player.select_weapon(idx)
        # reload
        w = player.weapon
        if k[pygame.K_r] and w.start_reload():
            self.audio.play("reload")
        # firing
        auto = w.fire_mode == "auto"
        if self.input.mouse_down and (auto or self.input.mouse_pressed):
            self.combat.fire(player, aim, self.audio, self.particles)
            self.wm.controller.emit_noise(player.x, player.y, 19.0, 1.6)
        elif self.input.mouse_pressed and w.is_empty():
            if w.start_reload():
                self.audio.play("reload")
        # Weather masks hearing and visibility for this simulation step.
        self.wm.controller.rain_amount = (
            self.renderer.weather.rain_amount if self.renderer else 0.0)
        # zombies
        self.wm.controller.update(dt)
        player.z = self.wm.world.height_at(player.x, player.y) * config.TERRAIN_HEIGHT_SCALE
        # Reward a clean escape with a short recovery window.
        nearby_threats = sum(
            1 for z in self.wm.controller.zombies
            if z.alive and not getattr(z, "spawning", False)
            and z.dist((player.x, player.y)) < 9.0)
        if (self.horror is not None and self._last_nearby_threats >= 2
                and nearby_threats == 0):
            self.horror.begin_recovery(14.0)
        self._last_nearby_threats = nearby_threats
        # bullets
        killed = self.combat.update(dt, self.wm.controller.zombies,
                                    self.particles, self.audio)
        for z in killed:
            self.wm.controller.kill(z)
            self.progression.on_kill(z)
            if self.survival is not None:
                self.survival.add_scrap(1)
        self.wm.controller.zombies = [z for z in self.wm.controller.zombies
                                       if z.alive]
        # pickups
        for p in self.wm.player_pickup_zone(player):
            apply_pickup(player, p, self.audio, self.survival)
        # progression + world + particles
        self.progression.update(dt, player, self.wm.controller, self.wm.world)
        if self.horror is not None:
            horror_msg = self.horror.update(
                dt, player, self.wm.controller, self.progression,
                self.survival,
                self.wm.controller.noise_radius,
                self.renderer.weather.rain_amount if self.renderer else 0.0)
            if horror_msg is not None:
                if "branch" in horror_msg.lower():
                    self.audio.play("branch_snap")
                else:
                    self.audio.play("forest_whisper")
                if self.renderer is not None:
                    # A restrained visual sting; keep the scene sharp.
                    self.renderer.post.on_event(1.0)
                    self.renderer.shake.add(2.5, 0.8)
        # Sustained gunfire draws a delayed horde from distant spawn lanes.
        if self.hordes is not None:
            spawned = self.hordes.update(
                dt, player, self.wm.controller, self.progression.time,
                self.wm.controller.noise_radius,
                self.wm.controller.noise_timer)
            if spawned:
                self.progression.notify(
                    "Gunfire echoes through the forest. Something is coming.", 4.0)
        # Short, non-looping physiological cues; timers prevent repetition.
        self._update_survival_audio(dt, player)
        # dynamic combat/ambient music based on nearby threat
        self._update_dynamic_music(player)
        self.wm.world.update(dt)
        self.particles.update(dt, self.wm.world)
        # weather + flashlight battery (drives flicker / rain / fog visuals)
        if self.renderer is not None:
            self.renderer.set_battery(self.survival.flashlight_battery
                                     if self.survival else 100.0)
            self.renderer.tick_weather(dt, self.wm.world)
            self.audio.set_rain(self.renderer.weather.rain_amount)
        # camera follow
        cam.update(self.dt, player.x, player.y)
        # damage vignette
        if player.hp < self._prev_hp:
            self.hud.damage_pulse(1.0)
        self._prev_hp = player.hp
        # lose / win
        if self.progression.check_lose(player) or \
                self.progression.state == "won":
            self._enter_gameover()

    def _update_survival_audio(self, dt: float, player) -> None:
        """Trigger restrained heartbeat/breathing cues from survival pressure."""
        self._heartbeat_timer = max(0.0, self._heartbeat_timer - dt)
        self._breath_timer = max(0.0, self._breath_timer - dt)
        nearby = sum(
            1 for z in self.wm.controller.zombies
            if z.alive and not getattr(z, "spawning", False)
            and z.dist((player.x, player.y)) < 7.0)
        critical = player.hp <= 35.0 or nearby >= 3
        exhausted = (self.survival is not None
                     and self.survival.stamina <= 28.0)
        if critical and self._heartbeat_timer <= 0.0:
            self.audio.play("heartbeat")
            self._heartbeat_timer = 1.05 if player.hp <= 20.0 else 1.45
        if exhausted and self._breath_timer <= 0.0:
            self.audio.play("breathing")
            self._breath_timer = 1.65

    def _update_dynamic_music(self, player) -> None:
        """Crossfade between ambient and combat music based on threat."""
        if self.wm is None or self.progression is None:
            return
        close = 0
        for z in self.wm.controller.zombies:
            if not z.alive or getattr(z, "spawning", False):
                continue
            d2 = (z.x - player.x) ** 2 + (z.y - player.y) ** 2
            if d2 < 100.0:  # within ~10 tiles
                close += 1
                if d2 < 25.0 or z.state in ("attack", "pursue", "investigate"):
                    close += 1
        in_combat = close >= 3 or (self.progression.phase == "shrine"
                                   and self.wm.controller.alive_count > 0)
        target = "combat" if in_combat else "ambient"
        if self.audio.playing_music in ("menu", None):
            self.audio.play_music(target)
        elif self.audio.playing_music != target and self.state == "playing":
            self.audio.play_music(target)

    # ------------------------------------------------------------------
    def _render(self) -> None:
        has_world = self.renderer is not None and self.wm is not None
        if self.state in ("playing", "paused", "settings", "inventory") and has_world:
            tension = self.horror.tension if self.horror is not None else 0.0
            self.renderer.render_frame(self.wm.world, self.player,
                                       self.wm.controller.zombies,
                                       self.wm.active_pickups(),
                                       self.combat.bullets, self.dt,
                                       tension=tension,
                                       grenades=self.combat.grenades)
            self.hud.draw(self.screen, self.player, self.progression,
                          self.survival, self.story, self.dt,
                          horror=self.horror)
            if self.state == "paused" and self.pause_menu is not None:
                self.pause_menu.draw(self.screen, self.fonts)
            elif self.state == "settings" and self.settings_menu is not None:
                self.settings_menu.draw(self.screen, self.fonts)
            elif self.state == "inventory" and self.inventory_menu is not None:
                self.inventory_menu.draw(self.screen, self.player,
                                         self.survival, self.story)
        elif self.state == "settings":
            # Settings can be opened directly from the main menu, before a
            # world/renderer exists. Keep the cinematic menu visible beneath
            # the settings overlay instead of leaving the display black.
            self.audio.stop_rain()
            self._draw_menu_scene()
            if self.settings_menu is not None:
                self.settings_menu.draw(self.screen, self.fonts)
        elif self.state not in ("playing", "paused"):
            self.audio.stop_rain()
        if self.state == "menu":
            self._draw_menu_bg()
            self._draw_menu_scene()
        elif self.state == "gameover" and self.game_over is not None:
            won = self.progression.state == "won"
            self.game_over.draw(self.screen, self.fonts, won,
                                self.progression.score, self.progression.kills,
                                self.progression.time)

    def _draw_menu_bg(self) -> None:
        # The cinematic menu scene is fully painted by MainMenu itself;
        # this hook only clears leftovers when returning from other states.
        self.screen.fill((5, 10, 11))
