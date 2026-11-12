"""In-game heads-up display: health, weapon, ammo, objective, score."""
from __future__ import annotations

import pygame

from ui.widgets import FontSet, text


class HUD:
    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.W = screen_w
        self.H = screen_h
        self.fonts = FontSet()
        self.dmg_vignette = 0.0

    # ------------------------------------------------------------------
    def damage_pulse(self, amount: float) -> None:
        self.dmg_vignette = max(self.dmg_vignette, amount)

    # ------------------------------------------------------------------
    def draw(self, screen, player, progression, survival=None, story=None) -> None:
        f = self.fonts
        # health bar
        bw, bh = 220, 22
        bx, by = 24, 24
        ratio = max(0.0, player.hp / player.max_hp)
        pygame.draw.rect(screen, (30, 26, 22), (bx - 4, by - 4,
                                                 bw + 8, bh + 8),
                         border_radius=6)
        pygame.draw.rect(screen, (70, 40, 38), (bx, by, bw, bh),
                         border_radius=4)
        col = (150, 40, 40) if ratio < 0.3 else (190, 80, 50)
        pygame.draw.rect(screen, col, (bx, by, int(bw * ratio), bh),
                         border_radius=4)
        text(screen, f, f"HP {int(player.hp)}/{int(player.max_hp)}", bx + 10,
             by + bh // 2 + 1, 20, (240, 235, 225), "left", True)

        # weapon + ammo (bottom-left)
        w = player.weapon
        wx, wy = 24, self.H - 64
        pygame.draw.rect(screen, (30, 26, 22, 200),
                         (wx - 8, wy - 8, 300, 56), border_radius=8)
        text(screen, f, w.name, wx, wy + 6, 24, (240, 230, 210), "left",
             True)
        col = (240, 200, 120) if w.mag > 0 else (200, 90, 70)
        if w.reloading:
            col = (150, 150, 120)
            text(screen, f, "RELOADING", wx + 130, wy + 6, 20, col)
        text(screen, f, f"{w.mag} / {w.reserve}", wx + 130, wy + 6, 24,
             col, "left", True)
        # weapon slots
        for i, ww in enumerate(player.weapons):
            sel = i == player.current
            rx = wx + 120 + i * 58
            pygame.draw.rect(
                screen, (60, 56, 48) if sel else (38, 35, 30),
                (rx, wy + 30, 50, 20), border_radius=4)
            text(screen, f, str(i + 1), rx + 10, wy + 40, 18,
                 (220, 210, 180) if sel else (120, 110, 90), "left",
                 True)

        # Survival resources: sprint stamina and flashlight charge.
        if survival is not None:
            text(screen, f, f"STAMINA {survival.stamina_percent}%", 24, 78,
                 18, (190, 205, 160), "left")
            light_state = "ON" if survival.flashlight_on else "OFF / CHARGING"
            text(screen, f, f"LIGHT {survival.battery_percent}%  {light_state}",
                 24, 101, 17, (225, 205, 145), "left")
        if story is not None:
            text(screen, f, f"CLUES {len(story.discovered)}/{len(story.clues)}  [E] INVESTIGATE",
                 self.W // 2, self.H - 24, 17, (205, 190, 155), "center")

        # objective (top-centre)
        text(screen, f, progression.objective, self.W // 2, 30, 22,
             (235, 225, 200), "center")

        # score / wave / time (top-right)
        rx = self.W - 24
        text(screen, f, f"Wave {progression.wave}" if progression.phase ==
             "shrine" else f"Kills {progression.kills}", rx, 30, 22,
             (240, 210, 120), "right", True)
        text(screen, f, f"Score {progression.score}", rx, 54, 20,
             (210, 200, 180), "right")

        # temporary message
        if progression.message_timer > 0:
            a = min(1.0, progression.message_timer)
            text(screen, f, progression.message, self.W // 2, 90, 26,
                 (255, 240, 200), "center", True)

        # damage vignette
        if self.dmg_vignette > 0:
            v = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            a = int(140 * self.dmg_vignette)
            pygame.draw.rect(v, (160, 20, 10, a), (0, 0, self.W, 40))
            pygame.draw.rect(v, (160, 20, 10, a),
                             (0, self.H - 40, self.W, 40))
            screen.blit(v, (0, 0))
            self.dmg_vignette = max(0.0, self.dmg_vignette - 0.02)
