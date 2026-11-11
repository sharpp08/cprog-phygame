"""Settings: volumes, resolution, fullscreen, quality, camera zoom, controls."""
from __future__ import annotations

from typing import Optional

import pygame

import config
from ui.widgets import Button, FontSet, Slider, text


class SettingsMenu:
    RES_NAMES = [f"{w}x{h}" for (w, h) in config.RESOLUTIONS]
    QUAL_NAMES = list(config.QUALITY)

    def __init__(self, w: int, h: int, settings: dict, audio=None) -> None:
        self.W = w
        self.H = h
        self.settings = settings
        self.audio = audio
        self.fonts = FontSet()
        self._back_target = "main_menu"
        lx = 80
        self.sliders = [
            Slider("Master volume", lx, 150, 260, settings.get("master", 0.8),
                   0.0, 1.0, 0.1, self._on_master),
            Slider("Music volume", lx, 210, 260, settings.get("music", 0.6),
                   0.0, 1.0, 0.1, self._on_music),
            Slider("SFX volume", lx, 270, 260, settings.get("sfx", 0.8),
                   0.0, 1.0, 0.1, self._on_sfx),
            Slider("Camera zoom", lx, 330, 260,
                   settings.get("zoom", config.DEFAULT_ZOOM),
                   config.ZOOM_MIN, config.ZOOM_MAX, 0.05, self._on_zoom),
        ]
        # right column: resolution / fullscreen / quality
        rx = 520
        self.res_button = Button(
            f"Resolution: {self.RES_NAMES[settings.get('resolution', 1)]}",
            rx, 150, 240, 44, lambda: None)
        self.fs_button = Button(
            "Fullscreen: " + str(bool(settings.get("fullscreen", False))),
            rx, 204, 240, 44, lambda: None)
        self.q_button = Button(
            "Graphics: " + self.QUAL_NAMES[settings.get("quality", 1)],
            rx, 258, 240, 44, lambda: None)
        self.back = Button("Back", 44, self.H - 80, 160, 52, lambda: None)

    # ------------------------------------------------------------------
    def set_back_target(self, target: str) -> None:
        self._back_target = target

    def _on_master(self, v):
        self.settings["master"] = v
        self._apply_audio()

    def _on_music(self, v):
        self.settings["music"] = v
        self._apply_audio()

    def _on_sfx(self, v):
        self.settings["sfx"] = v
        self._apply_audio()

    def _on_zoom(self, v):
        self.settings["zoom"] = v

    def _apply_audio(self) -> None:
        if self.audio:
            self.audio.set_volumes(
                self.settings.get("master", 0.8),
                self.settings.get("music", 0.6),
                self.settings.get("sfx", 0.8))

    # ------------------------------------------------------------------
    def handle(self, event) -> Optional[str]:
        for s in self.sliders:
            s.handle(event, None, self.fonts)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.res_button.rect.collidepoint(event.pos):
                i = (self.settings.get("resolution", 1) + 1) % len(
                    self.RES_NAMES)
                self.settings["resolution"] = i
                self._refresh_labels()
            elif self.fs_button.rect.collidepoint(event.pos):
                self.settings["fullscreen"] = not \
                    self.settings.get("fullscreen", False)
                self._refresh_labels()
            elif self.q_button.rect.collidepoint(event.pos):
                self.settings["quality"] = \
                    (self.settings.get("quality", 1) + 1) % 3
                self._refresh_labels()
            elif self.back.rect.collidepoint(event.pos):
                return "back"
        return None

    def _refresh_labels(self) -> None:
        self.res_button.label = "Resolution: " + \
            self.RES_NAMES[self.settings.get("resolution", 1)]
        self.fs_button.label = "Fullscreen: " + \
            str(bool(self.settings.get("fullscreen", False)))
        self.q_button.label = "Graphics: " + \
            self.QUAL_NAMES[self.settings.get("quality", 1)]

    # ------------------------------------------------------------------
    def draw(self, screen, fonts: FontSet) -> None:
        text(screen, fonts, "Settings", self.W // 2, 70, 48,
             (240, 220, 160), "center", True)
        for s in self.sliders:
            s.draw(screen, fonts)
        for b in (self.res_button, self.fs_button, self.q_button):
            b.draw(screen, fonts)
        # controls reference
        text(screen, fonts,
             "Move: WASD / arrows   Run: Shift   Aim: Mouse\n"
             "Fire: LMB (hold to auto)   Reload: R   Switch: 1/2/3\n"
             "Pause: ESC / P", 520, 340, 20, (180, 170, 150))
        self.back.draw(screen, fonts)
