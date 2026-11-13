"""In-game heads-up display: health, weapon, ammo, objective, score."""
from __future__ import annotations

import math

import pygame

from ui.widgets import FontSet, text


class HUD:
    """Survival-horror HUD: animated bars, subtle warning pulses.

    All bars ease toward their target value each frame (no snapping),
    the health bar pulses red under 30% HP and the damage vignette is a
    restrained edge glow rather than a full-screen red flash.
    """

    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.W = screen_w
        self.H = screen_h
        self.fonts = FontSet()
        self.dmg_vignette = 0.0
        # eased display values (start at full so the first frame is sane)
        self._hp_r = 1.0
        self._st_r = 1.0
        self._bat_r = 1.0
        self._beat = 0.0
        self._bar_bg = pygame.Surface((220, 22), pygame.SRCALPHA)

    # ------------------------------------------------------------------
    def damage_pulse(self, amount: float) -> None:
        self.dmg_vignette = max(self.dmg_vignette, amount)

    # ------------------------------------------------------------------
    def _ease(self, cur: float, target: float, dt: float, rate: float):
        return cur + (target - cur) * min(1.0, dt * rate)

    @staticmethod
    def _bar(screen, x, y, w, h, ratio, color, label, fonts, flash=False):
        ratio = max(0.0, min(1.0, ratio))
        self_bg = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
        self_bg.fill((12, 10, 8, 150))
        screen.blit(self_bg, (x - 4, y - 4))
        pygame.draw.rect(screen, (40, 36, 30), (x, y, w, h),
                         border_radius=4)
        pw = int(w * ratio)
        if pw > 0:
            if flash:
                pulse = 0.75 + 0.25 * abs(math.sin(pygame.time.get_ticks()
                                                   * 0.0045))
                col = tuple(int(c * pulse) for c in color)
            else:
                col = color
            pygame.draw.rect(screen, col, (x, y, pw, h), border_radius=4)
        text(screen, fonts, label, x + 8, y + h // 2 + 1, 18,
             (235, 228, 214), "left", True)


    # ------------------------------------------------------------------
    def draw(self, screen, player, progression, survival=None, story=None,
             dt: float = 0.016, horror=None) -> None:
        f = self.fonts
        dt = max(0.001, min(0.1, float(dt)))
        ratio = max(0.0, player.hp / max(1.0, player.max_hp))
        self._hp_r = self._ease(self._hp_r, ratio, dt, 5.0)
        low = ratio < 0.3
        # health bar (pulses while critical)
        bw, bh = 220, 22
        bx, by = 24, 24
        col = (170, 40, 34) if low else (190, 80, 50)
        self._bar(screen, bx, by, bw, bh, self._hp_r, col,
                  f"HP {int(player.hp)}/{int(player.max_hp)}", f,
                  flash=low)
        if low:
            text(screen, f, "VITALS CRITICAL", bx + 2, by + bh + 6, 14,
                 (200, 60, 50) if int(pygame.time.get_ticks() * 0.003)
                 % 2 else (120, 40, 36), "left")
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
        # survival resource bars: eased stamina + flashlight battery
        if survival is not None:
            self._st_r = self._ease(self._st_r,
                                    survival.stamina /
                                    survival.max_stamina,
                                    dt, 6.0)
            self._bat_r = self._ease(self._bat_r,
                                     survival.flashlight_battery / 100.0,
                                     dt, 6.0)
            self._bar(screen, 24, 74, 150, 12, self._st_r,
                      (120, 140, 90), "STAMINA", f)
            bat_col = (225, 205, 145)
            if survival.flashlight_battery < 25:
                bat_col = (210, 120, 80)
            self._bar(screen, 24, 94, 150, 12, self._bat_r, bat_col,
                      "LANTERN " +
                      ("ON" if survival.flashlight_on else "OFF"), f,
                      flash=survival.flashlight_battery < 25)
            text(screen, f, f"SCRAP {survival.scrap}  [C] CRAFT MEDKIT (3)",
                 24, 124, 16, (190, 170, 135), "left")
            text(screen, f, "[CTRL] CROUCH / REDUCE NOISE",
                 24, 146, 14, (145, 155, 135), "left")
        if story is not None:
            clue_hint = ""
            try:
                px, py = player.x, player.y
                nearest = None
                for i, clue in enumerate(story.clues):
                    if i in story.discovered:
                        continue
                    d2 = (px - clue["pos"][0]) ** 2 + (py - clue["pos"][1]) ** 2
                    if nearest is None or d2 < nearest:
                        nearest = d2
                if nearest is not None and nearest <= 4.0:
                    clue_hint = "  -  [E] INVESTIGATE NEARBY"
            except Exception:
                clue_hint = ""
            text(screen, f, f"CLUES {len(story.discovered)}/{len(story.clues)}  [E] INVESTIGATE{clue_hint}",
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
        if horror is not None:
            threat_colors = {"quiet": (125, 145, 125),
                             "uneasy": (190, 175, 110),
                             "danger": (220, 130, 75),
                             "critical": (225, 75, 65)}
            level = getattr(horror, "level", "quiet")
            text(screen, f, f"THREAT  {level.upper()}", rx, 80, 16,
                 threat_colors.get(level, (180, 170, 150)), "right", True)

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
