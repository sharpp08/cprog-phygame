"""Cinematic main menu for the forest survival experience.

The background is composed once per resolution into cached static layers
(sky, moon, forest bands, clearing, shrine, pond, foreground) and only the
cheap animated elements (fog, ripples, swaying grass, drifting clouds,
dust motes, button hover states) are redrawn each frame using delta time.
"""
from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame

from ui.widgets import Button, FontSet, text


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


class MainMenu:
    # Palette ------------------------------------------------------------
    _SKY_TOP = (4, 9, 12)
    _SKY_BOT = (13, 23, 24)
    _HORIZON = (52, 44, 32)
    _FOG = (151, 170, 151)
    _INK = (230, 224, 197)
    _INK_DIM = (169, 184, 160)
    _ACCENT = (191, 112, 82)
    _GOLD = (180, 153, 101)

    def __init__(self, w: int, h: int, has_save: bool) -> None:
        self.W, self.H = w, h
        self.fonts = FontSet()
        self.has_save = has_save
        self.time = 0.0

        # --- layout: buttons ------------------------------------------------
        bw = min(350, max(230, int(w * .29)))
        bh = max(48, min(58, int(h * .075)))
        gap = max(9, int(h * .018))
        x = int(w * .105)
        y0 = int(h * .505)
        self.buttons = [
            ("New Game", Button("NEW GAME", x, y0, bw, bh, None)),
            ("Continue", Button("CONTINUE", x, y0 + bh + gap, bw, bh, None)),
            ("Settings", Button("SETTINGS", x, y0 + 2 * (bh + gap), bw, bh, None)),
            ("Exit", Button("EXIT", x, y0 + 3 * (bh + gap), bw, bh, None)),
        ]
        self.buttons[1][1].enabled = has_save
        self._hover_t = {name: 0.0 for name, _ in self.buttons}
        self._press_flash = 0.0

        # --- animated entity tables (positions computed in world coords) -----
        self._grass: List[Tuple[int, int, int, int]] = []
        self._motes: List[Tuple[float, float, float, float]] = []
        self._ripples: List[Tuple[float, float, float, float]] = []
        self._fog_band_seed: List[Tuple[float, float, float, float]] = []

        # --- cached static scene --------------------------------------------
        self._bg_static: Optional[pygame.Surface] = None
        self._cloud_sheet: Optional[pygame.Surface] = None
        self._panel_tex: Optional[pygame.Surface] = None
        self._build_scene(w, h)

    # ======================================================================
    # Scene construction (cached; rebuilt only on resolution change)
    # ======================================================================
    def _build_scene(self, w: int, h: int) -> None:
        rng = random.Random(1937 + w * 7 + h * 13)  # stable per resolution
        self.W, self.H = w, h

        bg = pygame.Surface((w, h)).convert()

        # --- 1. twilight sky + amber horizon --------------------------------
        horizon_y = int(h * .62)
        for y in range(0, h, 2):
            q = y / max(1, h)
            if y < horizon_y:
                t = y / max(1, horizon_y)
                col = tuple(int(_lerp(self._SKY_TOP[i], self._HORIZON[i],
                                      _smoothstep(t) * .8)) for i in range(3))
            else:
                t = (y - horizon_y) / max(1, h - horizon_y)
                col = tuple(int(_lerp(self._HORIZON[i], self._SKY_BOT[i], t))
                            for i in range(3))
            pygame.draw.line(bg, col, (0, y), (w, y + 1))

        # --- 2. stars (fade near horizon, twinkle at draw time) --------------
        self._stars = []
        for _ in range(70):
            sx = rng.randrange(0, w)
            sy = rng.randrange(0, int(h * .42))
            fade = 1.0 - (sy / (h * .5))
            self._stars.append((sx, sy, rng.uniform(.5, 1.6),
                                rng.uniform(0, math.tau),
                                max(.15, fade)))

        # --- 3. moon + halo ---------------------------------------------------
        mx, my = int(w * .78), int(h * .22)
        self._moon = (mx, my)
        halo_r = int(h * .30)
        halo = pygame.Surface((halo_r * 2, halo_r * 2), pygame.SRCALPHA)
        hc = halo_r
        for radius, alpha in ((halo_r, 5), (int(halo_r * .72), 9),
                              (int(halo_r * .46), 15),
                              (int(halo_r * .26), 24)):
            pygame.draw.circle(halo, (170, 186, 160, alpha), (hc, hc), radius)
        bg.blit(halo, (mx - hc, my - hc))
        r_moon = max(16, h // 36)
        pygame.draw.circle(bg, (146, 160, 140), (mx, my), r_moon)
        pygame.draw.circle(bg, (188, 194, 168), (mx - 3, my - 4),
                           int(r_moon * .78))
        for _ in range(5):  # faint maria
            a = rng.uniform(0, math.tau)
            d = rng.uniform(0, r_moon * .5)
            pygame.draw.circle(bg, (128, 142, 124),
                               (int(mx + math.cos(a) * d),
                                int(my + math.sin(a) * d)),
                               rng.randint(2, max(3, r_moon // 5)))

        # --- 4. forest bands with atmospheric perspective ---------------------
        bands = [
            # (base_y, count, color, h_min, h_max, w_min, w_max, detail)
            (h * .58, 14, (22, 38, 33), .20, .30, 9, 14, True),
            (h * .66, 18, (13, 28, 25), .24, .38, 11, 18, True),
            (h * .75, 22, (6, 15, 15),  .28, .46, 14, 24, False),
        ]
        for bi, (base, count, col, hmin, hmax, wmin, wmax, detail) in enumerate(bands):
            base = int(base)
            for i in range(count):
                seed = i * 83 + bi * 47
                x = int((seed * 37 + i * 61) % (w + 160)) - 80
                th = int(h * rng.uniform(hmin, hmax))
                tw = rng.randint(wmin, wmax)
                lean = rng.uniform(-6, 6)
                # trunk
                pygame.draw.polygon(bg, col, [
                    (x - tw, base + 4), (x - tw // 2 + lean * .3, base - th * .7),
                    (x - 2 + lean, base - th), (x + 3 + lean, base - th * .95),
                    (x + tw // 2 + lean * .3, base - th * .68),
                    (x + tw, base + 4)])
                # root flare
                pygame.draw.polygon(bg, col, [
                    (x - tw - 6, base + 4), (x - tw // 2, base - 2),
                    (x + tw // 2, base - 2), (x + tw + 6, base + 4)])
                # branches
                nb = rng.randint(2, 4) if detail else 1
                for b in range(nb):
                    by = base - th * rng.uniform(.5, .9)
                    bl = rng.uniform(.18, .4) * th
                    dirn = -1 if b % 2 else 1
                    pygame.draw.line(bg, col, (x + lean * .5, int(by)),
                                     (int(x + dirn * bl + lean), int(by - bl * .5)),
                                     max(2, tw // 3))
                    # needle clusters for conifers
                    if detail:
                        for k in range(3):
                            fx = int(x + dirn * bl * (k + 1) / 3 + lean)
                            fy = int(by - bl * .5 * (k + 1) / 3)
                            fw = int(bl * .35 * (1 - k / 4))
                            pygame.draw.line(bg, col, (fx - fw, fy + 4),
                                             (fx, fy), 2)
                            pygame.draw.line(bg, col, (fx + fw, fy + 4),
                                             (fx, fy), 2)
                # canopy clump
                if detail:
                    for c in range(rng.randint(2, 4)):
                        cx = x + lean + rng.randint(-tw * 2, tw * 2)
                        cy = base - th + rng.randint(-6, 10)
                        cw = rng.randint(tw * 2, tw * 4)
                        ch = rng.randint(8, 18)
                        pygame.draw.ellipse(bg, col, (cx - cw, cy - ch, cw * 2, ch * 2))

        # --- 5. clearing ground ------------------------------------------------
        ground_y = int(h * .83)
        clearing = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(clearing, (34, 45, 32, 235),
                            (int(w * .34), int(h * .55),
                             int(w * .78), int(h * .58)))
        # uneven terrain blotches
        for _ in range(26):
            bx = rng.randint(int(w * .40), int(w * .98))
            by = rng.randint(int(h * .60), int(h * .95))
            br = rng.randint(10, 34)
            shade = rng.randint(-8, 10)
            pygame.draw.ellipse(clearing, (34 + shade, 45 + shade, 32 + shade, 60),
                                (bx - br, by - br // 3, br * 2, br))

        # --- 6. pond -----------------------------------------------------------
        pond = pygame.Rect(int(w * .70), int(h * .665),
                           int(w * .235), int(h * .105))
        self._pond = pond
        pygame.draw.ellipse(clearing, (18, 36, 38, 235), pond)
        # depth gradient toward the middle
        inner = pond.inflate(-pond.w // 5, -pond.h // 3)
        pygame.draw.ellipse(clearing, (12, 26, 30, 160), inner)
        # moonlit rim
        pygame.draw.ellipse(clearing, (120, 148, 128, 90),
                            pygame.Rect(pond.x, pond.y, pond.w, pond.h), 2)
        # lily pads
        for _ in range(6):
            lx = rng.randint(pond.x + 8, pond.right - 16)
            ly = rng.randint(pond.y + 6, pond.bottom - 10)
            lr = rng.randint(3, 6)
            pygame.draw.ellipse(clearing, (44, 74, 46, 220),
                                (lx - lr, ly - lr // 2, lr * 2, lr))
            pygame.draw.line(clearing, (58, 92, 56, 220),
                             (lx, ly), (lx + lr - 1, ly), 1)
        # reeds on the near bank
        for i in range(14):
            rx = pond.x + 4 + (i * 37) % max(1, pond.w - 8)
            ry = pond.bottom - rng.randint(0, 8)
            rh = rng.randint(10, 22)
            col = (52, 78, 50, 200) if i % 2 else (78, 96, 58, 190)
            pygame.draw.line(clearing, col, (rx, ry), (rx - 2, ry - rh), 2)
            pygame.draw.circle(clearing, (96, 82, 52, 220),
                               (rx - 2, ry - rh), 2)

        # --- 7. worn dirt trail -------------------------------------------------
        path_pts = [
            (int(w * .62), ground_y + 8), (int(w * .66), int(h * .76)),
            (int(w * .61), int(h * .70)), (int(w * .55), int(h * .66)),
            (int(w * .52), int(h * .61))]
        pygame.draw.lines(clearing, (88, 70, 48, 200), False, path_pts,
                          max(14, int(h * .026)))
        pygame.draw.lines(clearing, (140, 112, 74, 90), False, path_pts,
                          max(2, int(h * .004)))
        # scattered stones along the trail
        for i in range(9):
            t = i / 8.0
            px = int(_lerp(path_pts[0][0], path_pts[-1][0], t)) + rng.randint(-14, 14)
            py = int(_lerp(path_pts[0][1], path_pts[-1][1], t)) + rng.randint(-6, 6)
            sr = rng.randint(2, 5)
            pygame.draw.ellipse(clearing, (70, 74, 64, 210),
                                (px - sr, py - sr // 2, sr * 2, sr))
            pygame.draw.ellipse(clearing, (96, 100, 88, 120),
                                (px - sr, py - sr // 2, sr * 2, sr // 2))

        # --- 8. the ancient shrine (red-roofed landmark) -----------------------
        sx, sy = int(w * .585), int(h * .575)
        self._shrine = (sx, sy)
        # contact shadow
        pygame.draw.ellipse(clearing, (0, 0, 0, 120),
                            (sx - 46, sy + 28, 96, 22))
        # stone base + steps
        pygame.draw.rect(clearing, (58, 60, 54, 255),
                         (sx - 30, sy + 14, 60, 16))
        pygame.draw.rect(clearing, (72, 74, 66, 255),
                         (sx - 34, sy + 26, 68, 6))
        # wooden body, weathered planks
        pygame.draw.rect(clearing, (64, 44, 32, 255),
                         (sx - 24, sy - 10, 48, 26))
        for px in range(sx - 20, sx + 22, 8):
            pygame.draw.line(clearing, (48, 33, 24, 160),
                             (px, sy - 8), (px, sy + 14), 1)
        # doorway
        pygame.draw.rect(clearing, (16, 20, 16, 255),
                         (sx - 7, sy + 1, 14, 15))
        # distinctive red roof, gently curved
        pygame.draw.polygon(clearing, (122, 46, 32, 255), [
            (sx - 40, sy - 10), (sx - 28, sy - 26), (sx, sy - 40),
            (sx + 28, sy - 26), (sx + 40, sy - 10),
            (sx + 31, sy - 6), (sx, sy - 30), (sx - 31, sy - 6)])
        pygame.draw.line(clearing, (178, 84, 48, 255),
                         (sx - 36, sy - 11), (sx + 36, sy - 11), 2)
        pygame.draw.line(clearing, (200, 110, 60, 200),
                         (sx - 24, sy - 25), (sx + 24, sy - 25), 1)
        # ridge ornament
        pygame.draw.line(clearing, (150, 60, 36, 255),
                         (sx, sy - 40), (sx, sy - 46), 3)
        # warm ember glow inside the doorway
        pygame.draw.circle(clearing, (214, 140, 60, 90),
                           (sx, sy + 8), 13)
        # moss at the base
        for _ in range(7):
            gx = sx + rng.randint(-40, 40)
            gy = sy + rng.randint(24, 32)
            pygame.draw.ellipse(clearing, (48, 72, 44, 140),
                                (gx - 6, gy - 3, 12, 6))

        # --- 9. abandoned props: fallen log + lantern ----------------------------
        lx, ly = int(w * .44), int(h * .80)
        pygame.draw.ellipse(clearing, (0, 0, 0, 100),
                            (lx - 60, ly + 8, 130, 14))
        pygame.draw.line(clearing, (58, 44, 30, 255),
                         (lx - 58, ly), (lx + 62, ly - 6), 9)
        pygame.draw.line(clearing, (76, 58, 36, 255),
                         (lx - 58, ly - 2), (lx + 62, ly - 8), 3)
        pygame.draw.circle(clearing, (84, 62, 38, 255), (lx + 62, ly - 7), 6)
        pygame.draw.circle(clearing, (46, 34, 20, 255), (lx + 62, ly - 7), 3)
        for i in range(4):  # shelf mushrooms
            mxp = lx - 40 + i * 26
            pygame.draw.ellipse(clearing, (150, 128, 92, 220),
                                (mxp, ly - 10, 10, 5))
        self._lantern = (int(w * .565), int(h * .755))
        lnx, lny = self._lantern
        pygame.draw.line(clearing, (40, 38, 32, 255),
                         (lnx, lny), (lnx, lny - 26), 2)
        pygame.draw.rect(clearing, (52, 46, 36, 255),
                         (lnx - 5, lny - 34, 10, 12), border_radius=2)
        pygame.draw.rect(clearing, (214, 160, 80, 130),
                         (lnx - 3, lny - 32, 6, 8), border_radius=1)

        # --- 10. foreground grass tufts (positions cached, swayed at draw time) --
        self._grass = []
        for i in range(52):
            seed = i * 59
            gx = (seed * 29 + rng.randint(0, 20)) % max(1, w)
            gy = int(h * (.74 + ((seed * 13 + i * 7) % 20) / 100))
            self._grass.append((gx, gy, rng.randint(7, 16), i % 5))

        # roots and dead branches in the extreme foreground
        for i in range(10):
            rx = (i * 173 + 40) % max(1, w)
            ry = int(h * (.90 + (i % 3) * .03))
            pygame.draw.line(clearing, (5, 10, 10, 230),
                             (rx, ry), (rx + rng.randint(-30, 30), ry - rng.randint(4, 14)),
                             rng.randint(2, 4))

        bg.blit(clearing, (0, 0))

        # --- 11. vignette ---------------------------------------------------------
        vign = pygame.Surface((w, h), pygame.SRCALPHA)
        vw = max(18, int(min(w, h) * .045))
        for i in range(vw):
            a = int(70 * (1 - i / vw) ** 2)
            pygame.draw.rect(vign, (0, 0, 0, a),
                             (i, i, w - 2 * i, h - 2 * i), 1)
        bg.blit(vign, (0, 0))

        self._bg_static = bg

        # --- 12. drifting cloud sheet ----------------------------------------------
        ch = int(h * .5)
        sheet = pygame.Surface((w * 2, ch), pygame.SRCALPHA)
        for _ in range(26):
            cx = rng.randint(0, w * 2)
            cy = rng.randint(0, ch)
            cw = rng.randint(120, 340)
            chh = rng.randint(14, 34)
            pygame.draw.ellipse(sheet, (105, 125, 121, rng.randint(8, 20)),
                                (cx - cw, cy - chh, cw * 2, chh * 2))
        self._cloud_sheet = sheet
        self._cloud_h = ch

        # --- 13. weathered panel texture --------------------------------------------
        pw, ph = int(w * .46), int(h * .84)
        tex = pygame.Surface((pw, ph), pygame.SRCALPHA)
        tex.fill((4, 10, 9, 208))
        for _ in range(420):
            tx = rng.randint(0, pw - 1)
            ty = rng.randint(0, ph - 1)
            a = rng.randint(4, 14)
            tex.set_at((tx, ty), (120, 130, 110, a))
        # faint vertical wood grain streaks
        for _ in range(30):
            tx = rng.randint(0, pw - 1)
            pygame.draw.line(tex, (70, 80, 64, 10),
                             (tx, 0), (tx + rng.randint(-6, 6), ph), 1)
        self._panel_tex = tex
        self._panel_rect = pygame.Rect(int(w * .055), int(h * .075), pw, ph)

        # --- 14. fog / ripple / mote animation tables -------------------------------
        self._fog_band_seed = [(rng.uniform(0, 1), rng.uniform(.68, .92),
                                rng.uniform(60, 210), rng.uniform(4, 12))
                               for _ in range(9)]
        self._ripples = [(rng.uniform(0, 1), rng.uniform(0, 1),
                          rng.uniform(6, 20), rng.uniform(.12, .3))
                         for _ in range(5)]
        self._motes = [(rng.uniform(0, 1), rng.uniform(.1, .5),
                        rng.uniform(6, 20), rng.uniform(0, math.tau))
                       for _ in range(14)]

    def invalidate(self, w: int, h: int) -> None:
        """Force a scene rebuild (e.g. after a resolution change)."""
        if (w, h) != (self.W, self.H) or self._bg_static is None:
            self._build_scene(w, h)

    # ======================================================================
    # Input
    # ======================================================================
    def handle(self, event, audio=None) -> Optional[str]:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, button in self.buttons:
                if button.enabled and button.rect.collidepoint(event.pos):
                    if audio:
                        audio.play("ui")
                    self._press_flash = 1.0
                    return self._action(name)
        return None

    @staticmethod
    def _action(name: str) -> str:
        return {"New Game": "start", "Continue": "continue",
                "Settings": "settings", "Exit": "exit"}[name]

    # ======================================================================
    # Drawing
    # ======================================================================
    def _draw_background(self, screen, dt: float) -> None:
        w, h = screen.get_size()
        self.time += dt
        t = self.time

        screen.blit(self._bg_static, (0, 0))

        # --- stars twinkle -----------------------------------------------------
        star_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for sx, sy, r, phase, fade in self._stars:
            tw = .45 + .55 * (0.5 + 0.5 * math.sin(t * 1.7 + phase))
            a = int(120 * tw * fade)
            if a > 4:
                pygame.draw.circle(star_surf, (210, 216, 200, a),
                                   (sx, sy), max(1, int(r)))
        screen.blit(star_surf, (0, 0))

        # --- drifting broken cloud bands across the moon -------------------------
        cw = self._cloud_sheet.get_width()
        off1 = int((t * 6) % cw)
        off2 = int((t * 3.1 + cw * .5) % cw)
        cloud_layer = pygame.Surface((w, self._cloud_h), pygame.SRCALPHA)
        cloud_layer.blit(self._cloud_sheet, (-off1, 0))
        cloud_layer.blit(self._cloud_sheet, (cw - off1, 0))
        cloud_layer.blit(self._cloud_sheet, (-off2, 12))
        cloud_layer.blit(self._cloud_sheet, (cw - off2, 12))
        screen.blit(cloud_layer, (0, 0))

        # --- pond: moon glade + expanding ripples ---------------------------------
        pond = self._pond
        glade = pygame.Surface((w, h), pygame.SRCALPHA)
        gx = int(pond.x + pond.w * .62)
        gy = int(pond.y + pond.h * .42)
        pygame.draw.ellipse(glade, (150, 176, 158, 26),
                            (gx - pond.w // 5, gy - 5, pond.w // 2, 10))
        pygame.draw.ellipse(glade, (150, 176, 158, 16),
                            (gx - pond.w // 8, gy + 9, pond.w // 3, 6))
        for phase, fx, span, speed in self._ripples:
            k = ((t * speed + phase) % 1.0)
            rr = int(4 + k * span)
            a = int(46 * (1 - k))
            rx = int(pond.x + pond.w * (.25 + .5 * fx))
            ry = int(pond.y + pond.h * (.35 + .3 * ((phase * 7) % 1)))
            pygame.draw.ellipse(glade, (168, 190, 172, a),
                                (rx - rr * 2, ry - rr // 2, rr * 4, rr))
        screen.blit(glade, (0, 0))

        # --- layered fog moving through the forest --------------------------------
        mist = pygame.Surface((w, h), pygame.SRCALPHA)
        for i, (phase, fy, mw, speed) in enumerate(self._fog_band_seed):
            mx = int((t * speed + phase * (w + 480)) % (w + 480)) - 240
            my = int(h * fy)
            mh = int(26 + (i % 3) * 12)
            a = 10 + (i % 3) * 4
            pygame.draw.ellipse(mist, (*self._FOG, a),
                                (mx - mw, my - mh, mw * 2, mh * 2))
        screen.blit(mist, (0, 0))

        # --- swaying foreground grass (wind) ----------------------------------------
        grass_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for gx2, gy2, gl, phase in self._grass:
            sway = int(3 * math.sin(t * 1.3 + phase * 1.7))
            col = (52, 76, 50, 150) if phase % 2 else (92, 104, 62, 120)
            pygame.draw.line(grass_surf, col, (gx2, gy2),
                             (gx2 + sway - 2, gy2 - gl), 2)
            pygame.draw.line(grass_surf, col, (gx2 + 3, gy2),
                             (gx2 + sway + 4, gy2 - gl + 3), 1)
        screen.blit(grass_surf, (0, 0))

        # --- dust motes drifting in the moonlight -----------------------------------
        mote_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        mx0, my0 = self._moon
        for fx, fy, r, phase in self._motes:
            px = int(fx * w + 22 * math.sin(t * .5 + phase))
            py = int(fy * h + 14 * math.cos(t * .37 + phase * 1.3))
            a = int(30 + 22 * math.sin(t * .9 + phase))
            if a > 4:
                pygame.draw.circle(mote_surf, (196, 206, 180, a), (px, py),
                                   max(1, int(r * .16)))
        screen.blit(mote_surf, (0, 0))

        # --- lantern ember flicker ----------------------------------------------------
        lnx, lny = self._lantern
        flick = .5 + .5 * math.sin(t * 9.3) * math.sin(t * 3.7 + 1.2)
        ember = pygame.Surface((60, 60), pygame.SRCALPHA)
        pygame.draw.circle(ember, (222, 150, 64, int(30 + 26 * flick)),
                           (30, 30), int(9 + 4 * flick))
        pygame.draw.circle(ember, (238, 186, 96, int(60 + 50 * flick)),
                           (30, 30), 3)
        screen.blit(ember, (lnx - 30, lny - 50))

    def _draw_button(self, screen, fonts: FontSet, name: str,
                     button: Button, index: int, dt: float) -> None:
        hovered = button.enabled and button.rect.collidepoint(
            pygame.mouse.get_pos())
        target = 1.0 if hovered else 0.0
        self._hover_t[name] += (target - self._hover_t[name]) * min(1.0, dt * 10.0)
        ht = _smoothstep(self._hover_t[name])
        self._press_flash = max(0.0, self._press_flash - dt * 3.0)

        r = button.rect
        press = int(1 + self._press_flash * 2)

        # glow
        if ht > 0.01:
            glow = pygame.Surface((r.w + 32, r.h + 28), pygame.SRCALPHA)
            ga = int(14 + 22 * ht)
            pygame.draw.rect(glow, (177, 145, 87, ga),
                             (0, 0, glow.get_width(), glow.get_height()),
                             border_radius=10)
            screen.blit(glow, (r.x - 16, r.y - 14))

        # body: weathered dark plate with a soft drop shadow
        pygame.draw.rect(screen, (2, 5, 5), r.move(0, 3 + press),
                         border_radius=5)
        fill = tuple(int(_lerp(20, 30, ht)) for _ in range(3))             if button.enabled else (13, 20, 19)
        pygame.draw.rect(screen, fill, r, border_radius=5)
        edge = tuple(int(_lerp(c, 205, ht)) for c in (88, 112, 92))             if button.enabled else (43, 57, 49)
        pygame.draw.rect(screen, edge, r, 1, border_radius=5)

        # left accent bar slides in on hover
        accent = tuple(int(_lerp(c, 214, ht)) for c in (118, 136, 100))
        bar_h = int((r.h - 18) * (.55 + .45 * ht))
        pygame.draw.rect(screen, accent,
                         (r.x + 1, r.centery - bar_h // 2, 3, bar_h),
                         border_radius=2)

        # label shifts gently toward the accent on hover
        lx = r.x + 62 + int(4 * ht)
        ink = tuple(int(_lerp(c, 246, ht)) for c in (208, 210, 186))             if button.enabled else (91, 105, 91)
        text(screen, fonts, f"0{index + 1}", r.x + 25, r.centery,
             14, (177, 151, 101) if button.enabled else (77, 91, 79),
             "left", True)
        text(screen, fonts, button.label, lx, r.centery,
             21, ink, "left", True)

        if not button.enabled:
            text(screen, fonts, "NO FIELD RECORD", r.right - 14,
                 r.centery, 10, (91, 105, 91), "right", True)
        else:
            chev = "›"
            text(screen, fonts, chev, r.right - 22 - int(5 * ht),
                 r.centery - 1, 26, ink, "center", True)

        # animated underline sweep on hover
        if ht > 0.02:
            uw = int((r.w - 28) * ht)
            pygame.draw.line(screen, (195, 163, 105),
                             (r.x + 14, r.bottom - 3),
                             (r.x + 14 + uw, r.bottom - 3), 2)

    def _draw_panel(self, screen, fonts: FontSet) -> None:
        px, py, pw, ph = self._panel_rect
        screen.blit(self._panel_tex, (px, py))
        pygame.draw.rect(screen, (76, 98, 77), (px, py, pw, ph), 1,
                         border_radius=7)
        pygame.draw.line(screen, (180, 146, 91), (px + 22, py + 2),
                         (px + pw - 22, py + 2), 2)
        # corner notches
        for cx, cy in ((px, py), (px + pw, py)):
            pygame.draw.line(screen, (150, 122, 80),
                             (cx - (8 if cx == px + pw else -8), py),
                             (cx, py + 8), 2)

        left = int(self.W * .105)
        text(screen, fonts, "A SURVIVAL HORROR EXPERIENCE",
             left, int(self.H * .145), 14, self._GOLD, "left", True)
        text(screen, fonts, "WHEN THE", left, int(self.H * .235),
             max(40, min(68, self.W // 17)), self._INK, "left", True)
        text(screen, fonts, "WOODS BLEED", left, int(self.H * .315),
             max(40, min(68, self.W // 17)), self._ACCENT, "left", True)
        line_y = int(self.H * .385)
        pygame.draw.line(screen, (142, 117, 78), (left, line_y),
                         (left + min(340, int(self.W * .30)), line_y), 2)
        text(screen, fonts, "THE FOREST REMEMBERS.",
             left, int(self.H * .425), 17, self._INK_DIM, "left", True)
        text(screen, fonts, "STAY QUIET. WATCH THE DARK. SURVIVE.",
             left, int(self.H * .462), 12, (113, 133, 117), "left", True)

    def _threat_level(self) -> Tuple[str, float, Tuple[int, int, int]]:
        """Slowly drifting menu threat readout, with rare unsettling spikes."""
        t = self.time
        base = .34 + .10 * math.sin(t * .11) + .06 * math.sin(t * .043 + 2.1)
        spike = 0.0
        cyc = (t * .05) % 1.0
        if .88 < cyc < .94:
            spike = .45 * math.sin((cyc - .88) / .06 * math.pi)
        v = max(.08, min(1.0, base + spike))
        if v < .38:
            return "LOW", v, (122, 158, 106)
        if v < .60:
            return "RISING", v, (196, 158, 84)
        return "UNKNOWN", v, (196, 92, 70)

    def _draw_status_report(self, screen, fonts: FontSet) -> None:
        rx = int(self.W * .685)
        report_y = int(self.H * .585)
        report_w = min(int(self.W * .26), 320)
        report_h = int(self.H * .265)
        report = pygame.Surface((report_w, report_h), pygame.SRCALPHA)
        report.fill((4, 10, 10, 128))
        screen.blit(report, (rx, report_y))
        pygame.draw.line(screen, (151, 124, 81), (rx, report_y),
                         (rx + report_w, report_y), 2)
        pad = 15
        text(screen, fonts, "SURVIVAL STATUS  /  01",
             rx + pad, report_y + 20, 12, (190, 158, 101), "left", True)
        text(screen, fonts, "SHRINE SECTOR",
             rx + pad, report_y + 47, 21, (218, 207, 170), "left", True)
        text(screen, fonts, "The forest is overrun.",
             rx + pad, report_y + 73, 13, (164, 177, 157), "left")
        text(screen, fonts, "CURRENT OBJECTIVE",
             rx + pad, report_y + 100, 10, (120, 140, 122), "left", True)
        text(screen, fonts, "FOLLOW THE OLD TRAIL",
             rx + pad, report_y + 116, 13, (218, 196, 150), "left", True)
        text(screen, fonts, "REACH THE SHRINE",
             rx + pad, report_y + 132, 13, (218, 196, 150), "left", True)

        label, v, col = self._threat_level()
        text(screen, fonts, "THREAT LEVEL",
             rx + pad, report_y + 158, 10, (120, 140, 122), "left", True)
        bar = pygame.Rect(rx + pad, report_y + 172, report_w - pad * 2, 6)
        pygame.draw.rect(screen, (26, 34, 30), bar, border_radius=3)
        fill = bar.copy()
        fill.w = int(bar.w * v)
        pygame.draw.rect(screen, col, fill, border_radius=3)
        text(screen, fonts, label, rx + report_w - pad,
             report_y + 158, 11, col, "right", True)

    def draw(self, screen, fonts: FontSet, dt: float = 1.0 / 60.0) -> None:
        w, h = screen.get_size()
        self.invalidate(w, h)
        self._draw_background(screen, dt)
        self._draw_panel(screen, fonts)

        for i, (name, button) in enumerate(self.buttons):
            self._draw_button(screen, fonts, name, button, i, dt)

        self._draw_status_report(screen, fonts)

        text(screen, fonts, "WASD MOVE   /   MOUSE AIM   /   ESC PAUSE",
             int(w * .055), h - 22, 12, (105, 126, 113), "left")
        text(screen, fonts, "v0.9   /   NIGHTFALL", w - 24, h - 22, 12,
             (105, 126, 113), "right")
