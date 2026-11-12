"""The game: owns state, the loop, menus and ties every system together."""
from __future__ import annotations

from typing import Optional

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
from systems.enemy_ai import ZombieController
from systems.inventory import apply_pickup
from systems.navigation import Navigation
from systems.progression import Progression
from systems.horror_director import HorrorDirector
from systems.storytelling import StorySystem
from systems.survival import SurvivalSystem
from systems.save_manager import SaveManager
from ui.game_over import GameOver
from ui.hud import HUD
from ui.main_menu import MainMenu
from ui.pause_menu import PauseMenu
from ui.settings_menu import SettingsMenu
from ui.widgets import FontSet


class Game:
    def __init__(self, window) -> None:
        self.window = window
        self.screen = window.screen
        self.settings = {
            "master": config.MASTER_VOL, "music": config.MUSIC_VOL,
            "sfx": config.SFX_VOL, "resolution": config.DEFAULT_RESOLUTION,
            "fullscreen": config.FULLSCREEN, "quality": 1,
            "zoom": config.DEFAULT_ZOOM,
        }
        self.audio = AudioManager()
        self.assets = AssetManager()
        self.particles = ParticleSystem()
        self.input = InputManager()
        self.save_manager = SaveManager()
        self.fonts = FontSet()

        self.state = "menu"
        self._settings_return = "menu"
        self.running = True
        self.clock = pygame.time.Clock()
        self.dt = 1.0 / config.TARGET_FPS

        # menus
        self.main_menu = MainMenu(config.WINDOW_W, config.WINDOW_H,
                                  self.save_manager.has_save())
        self.pause_menu: Optional[PauseMenu] = None
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
        self._prev_hp = 0.0
        self._last = pygame.time.get_ticks()

    # ------------------------------------------------------------------
    def _init_audio(self) -> None:
        self.audio.init()
        self.audio.set_volumes(self.settings["master"], self.settings["music"],
                               self.settings["sfx"])

    # ------------------------------------------------------------------
    def apply_settings(self, apply_window: bool = True) -> None:
        self.assets.set_quality(int(self.settings["quality"]))
        if self.renderer is not None:
            self.renderer.quality = int(self.settings["quality"])
        if apply_window:
            self.window.set_mode(self.settings["resolution"],
                                self.settings["fullscreen"])
            self.screen = self.window.screen
            self.assets.build()
            self._rebind_game()
        self.audio.set_volumes(self.settings["master"],
                              self.settings["music"],
                              self.settings["sfx"])

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
    def start_new(self) -> None:
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
        self.cam = Camera(config.WINDOW_W, config.WINDOW_H,
                          zoom=self.settings["zoom"])
        self.cam.set_target(self.player.x, self.player.y)
        self.cam.clamp(0, 0, self.wm.world.W, self.wm.world.H)
        self.renderer = Renderer(self.screen, self.cam, self.assets,
                                 self.particles)
        self.renderer.quality = int(self.settings["quality"])
        w, h = self.screen.get_size()
        self.renderer.W, self.renderer.H = w, h
        self.renderer._prep_fog()
        self.hud = HUD(w, h)
        self._prev_hp = self.player.hp
        self.state = "playing"
        self.save_manager.delete()
        self.audio.play_music("ambient")
        self.progression.notify("Find the ancient shrine. Follow the path.")
        self._print_world_diagnostics()

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
        data = self.save_manager.load()
        if data is None:
            self.start_new()
            return False
        self._init_world()
        pd = data["player"]
        weapons = [Weapon.from_dict(w) for w in pd["weapons"]]
        self.player = Player(pd["x"], pd["y"], weapons=weapons)
        self.player.current = pd.get("current", 0)
        self.player.hp = pd.get("hp", config.PLAYER_MAX_HP)
        pg = data["progression"]
        self.wm.setup(self.player, self.audio, self.particles)
        self.combat = CombatSystem(self.wm.grid)
        self.progression = Progression()
        self.survival = SurvivalSystem()
        self.story = StorySystem(self.wm.world)
        self.horror = HorrorDirector()
        self.story.discovered.update(pg.get("clues", []))
        sd = data.get("survival", {})
        self.survival.stamina = float(sd.get("stamina", 100.0))
        self.survival.flashlight_battery = float(sd.get("flashlight_battery", 100.0))
        self.survival.flashlight_on = bool(sd.get("flashlight_on", True))
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
        self.cam = Camera(config.WINDOW_W, config.WINDOW_H,
                          zoom=self.settings["zoom"])
        self.cam.set_target(self.player.x, self.player.y)
        self.cam.clamp(0, 0, self.wm.world.W, self.wm.world.H)
        self.renderer = Renderer(self.screen, self.cam, self.assets,
                                 self.particles)
        self.renderer.quality = int(self.settings["quality"])
        w, h = self.screen.get_size()
        self.renderer.W, self.renderer.H = w, h
        self.renderer._prep_fog()
        self.hud = HUD(w, h)
        self._prev_hp = self.player.hp
        self.state = "playing"
        self.audio.play_music("ambient")
        return True

    # ------------------------------------------------------------------
    def _enter_gameover(self) -> None:
        self.state = "gameover"
        self.game_over = GameOver(config.WINDOW_W, config.WINDOW_H)
        if self.progression.state == "won" and self.story is not None:
            self.game_over.ending_title, self.game_over.ending_subtitle = self.story.ending()
        self.audio.stop_music()
        if self.progression.state == "won":
            self.save_manager.delete()
        else:
            self.save_manager.save(self.player, self.progression,
                                   self.settings, self.story, self.survival)

    # ------------------------------------------------------------------
    def run(self) -> None:
        self._init_audio()
        self.assets.build()
        self.audio.play_music("menu")
        while self.running:
            self._frame()
        pygame.quit()

    # ------------------------------------------------------------------
    def _frame(self) -> None:
        dt = min((pygame.time.get_ticks() - self._last) / 1000.0,
                 1.0 / config.MIN_FPS)
        self._last = pygame.time.get_ticks()
        self.dt = dt
        for event in pygame.event.get():
            self._on_event(event)
        self._update(dt)
        self._render()
        self.clock.tick(config.TARGET_FPS)
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
            if event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                if self.survival and self.survival.craft_medkit(self.player):
                    self.progression.notify("Field dressing crafted (+35 HP)", 2.5)
                    self.audio.play("pickup")
                elif self.survival:
                    self.progression.notify("Need 3 scrap and missing health to craft", 2.0)
            if InputManager.pause_pressed():
                self._open_pause()
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
        self.settings_menu = SettingsMenu(config.WINDOW_W, config.WINDOW_H,
                                          self.settings, self.audio)
        self.settings_menu.set_back_target(return_state)
        self.state = "settings"

    def _open_pause(self) -> None:
        self.pause_menu = PauseMenu(config.WINDOW_W, config.WINDOW_H)
        self.state = "paused"

    def _handle_pause_result(self, res) -> None:
        if res == "resume":
            self.state = "playing"
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
                                   self.settings)
        self.state = "menu"
        self.settings_menu = None
        self.pause_menu = None
        self.main_menu = MainMenu(config.WINDOW_W, config.WINDOW_H,
                                  self.save_manager.has_save())
        self.audio.play_music("menu")



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
        requested_run = InputManager.running()
        can_run = self.survival.update(dt, requested_run) if self.survival else True
        player.apply_movement(mv, requested_run and can_run, dt, self.wm.grid)
        player.update(dt)
        if player.footstep_sound:
            self.audio.play("footstep")
            if self.wm.controller:
                self.wm.controller.emit_noise(
                    player.x, player.y, 11.0 if player.running else 5.0,
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
        # zombies
        self.wm.controller.update(dt)
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
            apply_pickup(player, p, self.audio)
        # progression + world + particles
        self.progression.update(dt, player, self.wm.controller, self.wm.world)
        if self.horror is not None:
            self.horror.update(dt, player, self.wm.controller, self.progression)
        self.wm.world.update(dt)
        self.particles.update(dt, self.wm.world)
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

    # ------------------------------------------------------------------
    def _render(self) -> None:
        if self.state in ("playing", "paused", "settings") and \
                self.renderer is not None:
            self.renderer.render_frame(self.wm.world, self.player,
                                       self.wm.controller.zombies,
                                       self.wm.active_pickups(),
                                       self.combat.bullets, self.dt)
            self.hud.draw(self.screen, self.player, self.progression,
                          self.survival, self.story)
        if self.state == "menu":
            self._draw_menu_bg()
            self.main_menu.draw(self.screen, self.fonts)
        elif self.state == "paused":
            self.pause_menu.draw(self.screen, self.fonts)
        elif self.state == "settings" and self.settings_menu is not None:
            self._draw_menu_bg()
            self.settings_menu.draw(self.screen, self.fonts)
        elif self.state == "gameover" and self.game_over is not None:
            won = self.progression.state == "won"
            self.game_over.draw(self.screen, self.fonts, won,
                                self.progression.score, self.progression.kills,
                                self.progression.time)

    def _draw_menu_bg(self) -> None:
        self.screen.fill((26, 22, 18))
        w, h = self.screen.get_size()
        glow = pygame.Surface((w, 220), pygame.SRCALPHA)
        for y in range(220):
            a = int(55 * (1 - y / 220))
            pygame.draw.line(glow, (70, 60, 40, a), (0, y), (w, y))
        self.screen.blit(glow, (0, 0))


