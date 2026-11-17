"""Responsive, readable field settings interface."""
from __future__ import annotations

from typing import Optional
import pygame

import config
from ui.widgets import Button, FontSet, Slider, text


class SettingsMenu:
    RES_NAMES = [f"{w}x{h}" for (w, h) in config.RESOLUTIONS]
    QUAL_NAMES = list(config.QUALITY)

    def __init__(self, w: int, h: int, settings: dict, audio=None) -> None:
        self.W, self.H = w, h
        self.settings = settings
        self.audio = audio
        self.fonts = FontSet()
        self._back_target = "main_menu"
        self._layout()

    def _layout(self) -> None:
        """Position controls inside two distinct columns at any window size."""
        w, h = self.W, self.H
        margin = max(22, int(min(w, h) * 0.045))
        self.panel = pygame.Rect(margin, margin, w - 2 * margin,
                                 h - 2 * margin)
        inner_x = self.panel.x + max(34, int(w * 0.035))
        inner_w = self.panel.width - 2 * (inner_x - self.panel.x)
        gap = max(34, int(inner_w * 0.07))
        left_w = int((inner_w - gap) * 0.46)
        right_x = inner_x + left_w + gap
        right_w = inner_x + inner_w - right_x

        top = max(150, int(h * 0.215))
        row_gap = max(58, int(h * 0.095))
        slider_w = min(left_w - 18, 310)
        self.sliders = [
            Slider("Master volume", inner_x, top, slider_w,
                   self.settings.get("master", 0.8), 0.0, 1.0, 0.05,
                   self._on_master),
            Slider("Music volume", inner_x, top + row_gap, slider_w,
                   self.settings.get("music", 0.6), 0.0, 1.0, 0.05,
                   self._on_music),
            Slider("SFX volume", inner_x, top + row_gap * 2, slider_w,
                   self.settings.get("sfx", 0.8), 0.0, 1.0, 0.05,
                   self._on_sfx),
            Slider("Camera zoom", inner_x, top + row_gap * 3, slider_w,
                   self.settings.get("zoom", config.DEFAULT_ZOOM),
                   config.ZOOM_MIN, config.ZOOM_MAX, 0.05, self._on_zoom),
        ]

        button_w = min(right_w, 340)
        button_h = 46
        button_gap = 12
        self.res_button = Button(
            f"RESOLUTION   {self.RES_NAMES[self.settings.get('resolution', 1) % len(self.RES_NAMES)]}",
            right_x, top - 3, button_w, button_h, lambda: None)
        self.fs_button = Button(
            "FULLSCREEN   " + ("ON" if self.settings.get("fullscreen") else "OFF"),
            right_x, top + button_h + button_gap - 3, button_w, button_h,
            lambda: None)
        self.q_button = Button(
            "GRAPHICS   " + self.QUAL_NAMES[self.settings.get("quality", 1) % len(self.QUAL_NAMES)].upper(),
            right_x, top + 2 * (button_h + button_gap) - 3, button_w,
            button_h, lambda: None)
        self.pf_button = Button(
            "POST PROCESSING   " + self._pf_label().upper(),
            right_x, top + 3 * (button_h + button_gap) - 3, button_w,
            button_h, lambda: None)

        controls_y = top + 4 * (button_h + button_gap) + 12
        controls_h = max(104, min(142, h - controls_y - 112))
        self.controls_rect = pygame.Rect(right_x, controls_y,
                                         right_w, controls_h)
        back_w = min(180, max(140, int(w * 0.14)))
        self.back = Button("BACK", self.panel.x + 12,
                           self.panel.bottom - 58, back_w, 48, lambda: None)

    def _pf_label(self) -> str:
        v = self.settings.get("post_fx")
        return {None: "Auto", True: "On", False: "Off"}[v]

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

    def handle(self, event) -> Optional[str]:
        for slider in self.sliders:
            slider.handle(event, None, self.fonts)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.res_button.rect.collidepoint(event.pos):
                i = (self.settings.get("resolution", 1) + 1) % len(self.RES_NAMES)
                self.settings["resolution"] = i
                self._refresh_labels()
            elif self.fs_button.rect.collidepoint(event.pos):
                self.settings["fullscreen"] = not self.settings.get("fullscreen", False)
                self._refresh_labels()
            elif self.q_button.rect.collidepoint(event.pos):
                self.settings["quality"] = (self.settings.get("quality", 1) + 1) % len(self.QUAL_NAMES)
                self._refresh_labels()
            elif self.pf_button.rect.collidepoint(event.pos):
                cur = self.settings.get("post_fx")
                self.settings["post_fx"] = None if cur is None else not cur
                self._refresh_labels()
            elif self.back.rect.collidepoint(event.pos):
                return "back"
        return None

    def _refresh_labels(self) -> None:
        self.res_button.label = "RESOLUTION   " + self.RES_NAMES[self.settings.get("resolution", 1)]
        self.fs_button.label = "FULLSCREEN   " + ("ON" if self.settings.get("fullscreen") else "OFF")
        self.q_button.label = "GRAPHICS   " + self.QUAL_NAMES[self.settings.get("quality", 1)].upper()
        self.pf_button.label = "POST PROCESSING   " + self._pf_label().upper()

    def draw(self, screen, fonts: FontSet) -> None:
        w, h = screen.get_size()
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((2, 7, 7, 205))
        screen.blit(shade, (0, 0))

        pygame.draw.rect(screen, (7, 16, 15), self.panel, border_radius=9)
        pygame.draw.rect(screen, (78, 99, 80), self.panel, 1, border_radius=9)
        # Restrained top and bottom rules frame the screen.
        pygame.draw.line(screen, (151, 126, 82),
                         (self.panel.x + 26, self.panel.y + 2),
                         (self.panel.right - 26, self.panel.y + 2), 2)

        text(screen, fonts, "FIELD SETTINGS", w // 2, 76, 38,
             (229, 218, 184), "center", True)
        text(screen, fonts, "AUDIO     /     DISPLAY     /     CONTROLS",
             w // 2, 111, 14, (137, 158, 139), "center", True)

        # Separate column surfaces prevent labels and controls from colliding.
        left_x = self.sliders[0].x - 22
        left_y = self.sliders[0].y - 42
        left_right = self.sliders[0].track.right + 22
        left_bottom = self.sliders[-1].track.bottom + 26
        left_card = pygame.Rect(left_x, left_y, left_right - left_x,
                                left_bottom - left_y)
        right_card = pygame.Rect(self.res_button.rect.x - 18,
                                 self.res_button.rect.y - 42,
                                 self.controls_rect.right - self.res_button.rect.x + 36,
                                 self.controls_rect.bottom - self.res_button.rect.y + 54)
        for card in (left_card, right_card):
            pygame.draw.rect(screen, (10, 22, 20), card, border_radius=7)
            pygame.draw.rect(screen, (43, 65, 54), card, 1, border_radius=7)

        text(screen, fonts, "SOUND & CAMERA", left_card.x + 16,
             left_card.y + 22, 15, (185, 157, 104), "left", True)
        text(screen, fonts, "DISPLAY & GRAPHICS", right_card.x + 16,
             right_card.y + 22, 15, (185, 157, 104), "left", True)

        for slider in self.sliders:
            slider.draw(screen, fonts)
        for button in (self.res_button, self.fs_button, self.q_button,
                       self.pf_button):
            button.draw(screen, fonts)

        # Dedicated control legend, below the display buttons.
        cr = self.controls_rect
        pygame.draw.rect(screen, (13, 27, 24), cr, border_radius=5)
        pygame.draw.rect(screen, (57, 78, 64), cr, 1, border_radius=5)
        text(screen, fonts, "FIELD CONTROLS", cr.x + 14, cr.y + 17,
             14, (185, 157, 104), "left", True)
        line_y = cr.y + 40
        line_gap = 19
        controls = (
            "MOVE  WASD / ARROWS     RUN  SHIFT",
            "AIM  MOUSE     FIRE  LEFT CLICK",
            "RELOAD  R     SWITCH WEAPON  1 / 2 / 3",
            "PAUSE  ESC / P",
        )
        for i, line in enumerate(controls):
            if line_y + i * line_gap < cr.bottom - 5:
                text(screen, fonts, line, cr.x + 14,
                     line_y + i * line_gap, 13, (168, 184, 165), "left")

        self.back.draw(screen, fonts)
