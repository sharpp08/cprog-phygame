"""Cinematic main menu for the forest survival experience."""
from __future__ import annotations

from typing import Optional
import math
import pygame

from ui.widgets import Button, FontSet, text


class MainMenu:
    def __init__(self, w: int, h: int, has_save: bool) -> None:
        self.W, self.H = w, h
        self.fonts = FontSet()
        self.has_save = has_save
        self._stars = [
            (int((i * 193 + 37) % max(1, w)),
             int((i * 79 + 19) % max(1, int(h * .55))),
             .6 + (i % 5) * .22)
            for i in range(42)
        ]
        bw = min(350, max(230, int(w * .29)))
        bh, gap = max(48, min(58, int(h * .075))), max(9, int(h * .018))
        x = int(w * .105)
        y0 = int(h * .505)
        self.buttons = [
            ("New Game", Button("NEW GAME", x, y0, bw, bh, None)),
            ("Continue", Button("CONTINUE", x, y0 + bh + gap, bw, bh, None)),
            ("Settings", Button("SETTINGS", x, y0 + 2 * (bh + gap), bw, bh, None)),
            ("Exit", Button("EXIT", x, y0 + 3 * (bh + gap), bw, bh, None)),
        ]
        self.buttons[1][1].enabled = has_save

    def handle(self, event, audio=None) -> Optional[str]:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, button in self.buttons:
                if button.enabled and button.rect.collidepoint(event.pos):
                    if audio:
                        audio.play("ui")
                    return self._action(name)
        return None

    @staticmethod
    def _action(name: str) -> str:
        return {"New Game": "start", "Continue": "continue",
                "Settings": "settings", "Exit": "exit"}[name]

    def _draw_button(self, screen, fonts: FontSet, button: Button,
                     index: int) -> None:
        hovered = button.enabled and button.rect.collidepoint(pygame.mouse.get_pos())
        r = button.rect
        if hovered:
            glow = pygame.Surface((r.w + 28, r.h + 24), pygame.SRCALPHA)
            pygame.draw.rect(glow, (177, 145, 87, 25),
                             (0, 0, glow.get_width(), glow.get_height()),
                             border_radius=10)
            screen.blit(glow, (r.x - 14, r.y - 12))
        fill = (23, 34, 30) if button.enabled else (13, 20, 19)
        edge = (190, 158, 99) if hovered else ((83, 108, 88) if button.enabled else (43, 57, 49))
        ink = (246, 231, 194) if hovered else ((218, 219, 193) if button.enabled else (91, 105, 91))
        pygame.draw.rect(screen, (2, 5, 5), r.move(0, 4), border_radius=5)
        pygame.draw.rect(screen, fill, r, border_radius=5)
        pygame.draw.rect(screen, edge, r, 1, border_radius=5)
        accent = (198, 164, 99) if hovered else (105, 126, 96)
        pygame.draw.rect(screen, accent, (r.x + 1, r.y + 9, 3, r.h - 18),
                         border_radius=2)
        text(screen, fonts, f"0{index + 1}", r.x + 25, r.centery,
             14, (177, 151, 101) if button.enabled else (77, 91, 79),
             "left", True)
        text(screen, fonts, button.label, r.x + 62, r.centery,
             21, ink, "left", True)
        if not button.enabled:
            text(screen, fonts, "NO FIELD RECORD", r.right - 14,
                 r.centery, 10, (91, 105, 91), "right", True)
        else:
            text(screen, fonts, "›", r.right - 22,
                 r.centery - 1, 26, ink, "center", True)
        if hovered:
            pygame.draw.line(screen, (195, 163, 105),
                             (r.x + 14, r.bottom - 3),
                             (r.right - 14, r.bottom - 3), 2)

    def draw(self, screen, fonts: FontSet) -> None:
        w, h = screen.get_size()
        t = pygame.time.get_ticks() * .001
        screen.fill((5, 10, 11))

        # Layered twilight sky with a distant amber horizon.
        for y in range(0, h, 2):
            q = y / max(1, h)
            col = (int(5 + 17*q), int(11 + 14*q), int(17 + 7*q))
            pygame.draw.line(screen, col, (0, y), (w, y))

        # Broken cloud bands soften the moonlight instead of a clean flat moon.
        cloud = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(11):
            cx = int((i * 227 + t * (5 + i % 3)) % (w + 280)) - 140
            cy = int(h * (.13 + (i % 4) * .075))
            pygame.draw.ellipse(cloud, (105, 125, 121, 13),
                                (cx - 120, cy - 13, 240, 27))
        screen.blit(cloud, (0, 0))

        # Moon behind broken cloud: diffuse halo and restrained reflected light.
        moon = (int(w * .78), int(h * .24))
        halo = pygame.Surface((int(h * .72), int(h * .72)), pygame.SRCALPHA)
        hc = halo.get_width() // 2
        for radius, alpha in ((hc, 4), (int(hc*.76), 7),
                              (int(hc*.52), 11), (int(hc*.30), 17)):
            pygame.draw.circle(halo, (167, 184, 157, alpha), (hc, hc), radius)
        screen.blit(halo, (moon[0]-hc, moon[1]-hc))
        pygame.draw.circle(screen, (151, 165, 145), moon, max(18, h//34))
        pygame.draw.circle(screen, (184, 190, 165),
                           (moon[0]-4, moon[1]-5), max(13, h//43))

        # Deep forest silhouettes: irregular trunks, branches and layered canopies.
        for layer, count in ((0, 18), (1, 24), (2, 30)):
            base = int(h * (.66 + layer * .105))
            color = ((25, 42, 34), (12, 26, 23), (5, 12, 12))[layer]
            for i in range(count):
                seed = i * 83 + layer * 47
                x = int((seed * 37 + t * (1.2 + layer*1.5) *
                         (1 if i % 2 else -1)) % (w + 150)) - 75
                trunk_h = int(h * (.17 + (seed % 19) * .012))
                trunk_w = max(4, 10 - layer*2)
                pygame.draw.polygon(screen, color, [
                    (x-trunk_w, base), (x-trunk_w//2, base-trunk_h*.72),
                    (x-2, base-trunk_h), (x+3, base-trunk_h*.96),
                    (x+trunk_w//2, base-trunk_h*.68), (x+trunk_w, base)])
                for branch in (-1, 1):
                    pygame.draw.line(screen, color,
                        (x, base-trunk_h*.65),
                        (x+branch*(12+seed%18), base-trunk_h*.83),
                        max(2, trunk_w//2))

        # Game-world clearing: an isometric shrine approach, pond and stone path.
        ground_y = int(h * .83)
        clearing = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(clearing, (37, 48, 34, 210),
                            (int(w*.38), int(h*.57), int(w*.72), int(h*.55)))
        pygame.draw.ellipse(clearing, (23, 45, 43, 205),
                            (int(w*.69), int(h*.64), int(w*.25), int(h*.12)))
        # Moonlit pond rim and small water reflections.
        pygame.draw.ellipse(clearing, (73, 91, 69, 130),
                            (int(w*.69), int(h*.64), int(w*.25), int(h*.12)), 3)
        for i in range(8):
            rx = int(w*.72 + (i*31) % max(1,int(w*.18)))
            ry = int(h*(.69 + (i%3)*.018))
            pygame.draw.line(clearing, (119, 155, 151, 42),
                             (rx, ry), (rx+14, ry-2), 1)

        # Worn dirt trail leads toward the shrine clearing.
        path_pts = [
            (int(w*.62), ground_y), (int(w*.66), int(h*.75)),
            (int(w*.61), int(h*.69)), (int(w*.55), int(h*.65)),
            (int(w*.52), int(h*.60))]
        pygame.draw.lines(clearing, (91, 72, 49, 185), False, path_pts,
                          max(13, int(h*.025)))
        pygame.draw.lines(clearing, (139, 111, 73, 75), False, path_pts,
                          max(2, int(h*.004)))

        # Small shrine landmark, matching the game's forest-shrine setting.
        sx, sy = int(w*.59), int(h*.565)
        pygame.draw.ellipse(clearing, (0, 0, 0, 115),
                            (sx-42, sy+26, 90, 22))
        pygame.draw.rect(clearing, (69, 47, 33, 255),
                         (sx-27, sy-8, 54, 39))
        pygame.draw.polygon(clearing, (116, 48, 34, 255),
                            [(sx-37, sy-8), (sx, sy-34),
                             (sx+37, sy-8), (sx+29, sy-2),
                             (sx, sy-24), (sx-29, sy-2)])
        pygame.draw.line(clearing, (173, 119, 67, 255),
                         (sx-25, sy-6), (sx+25, sy-6), 2)
        pygame.draw.rect(clearing, (22, 28, 22, 255),
                         (sx-7, sy+8, 14, 23))
        pygame.draw.circle(clearing, (220, 164, 83, 110),
                           (sx, sy+3), 22, 2)

        # Foreground grass, roots and dead branches frame the playable clearing.
        for i in range(42):
            seed = i * 59
            gx = (seed * 29) % max(1, w)
            gy = int(h*(.73 + (seed%23)/100))
            col = (43, 65, 43, 110) if i%2 else (91, 103, 61, 90)
            pygame.draw.line(clearing, col, (gx, gy), (gx-4, gy-10-(i%5)), 2)
        screen.blit(clearing, (0, 0))

        # Moving ground fog hugs the clearing and waterline.
        mist = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(7):
            mx = int((t*(7+i*2)+i*w*.23)%(w+420))-210
            my = int(h*(.68+(i%4)*.055))
            pygame.draw.ellipse(mist, (151, 170, 151, 13),
                                (mx-210, my-18, 420, 58))
        screen.blit(mist, (0, 0))

        # Dark vignette makes the moonlit focal area and menu read clearly.
        vignette = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(vignette, (0, 0, 0, 74),
                         (0, 0, w, h), width=max(18, int(min(w, h) * .035)))
        screen.blit(vignette, (0, 0))

        # Main identity panel.
        px, py = int(w * .055), int(h * .075)
        pw, ph = int(w * .46), int(h * .84)
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((4, 10, 9, 205))
        screen.blit(panel, (px, py))
        pygame.draw.rect(screen, (76, 98, 77), (px, py, pw, ph), 1,
                         border_radius=7)
        pygame.draw.line(screen, (180, 146, 91), (px + 22, py + 2),
                         (px + pw - 22, py + 2), 2)

        left = int(w * .105)
        text(screen, fonts, "A SURVIVAL HORROR EXPERIENCE",
             left, int(h * .145), 14, (180, 153, 101), "left", True)
        text(screen, fonts, "WHEN THE", left, int(h * .235),
             max(40, min(68, w // 17)), (230, 224, 197), "left", True)
        text(screen, fonts, "WOODS BLEED", left, int(h * .315),
             max(40, min(68, w // 17)), (191, 112, 82), "left", True)
        line_y = int(h * .385)
        pygame.draw.line(screen, (142, 117, 78), (left, line_y),
                         (left + min(340, int(w * .30)), line_y), 2)
        text(screen, fonts, "THE FOREST REMEMBERS.",
             left, int(h * .425), 17, (169, 184, 160), "left", True)
        text(screen, fonts, "STAY QUIET. WATCH THE DARK. SURVIVE.",
             left, int(h * .462), 12, (113, 133, 117), "left", True)

        for i, (_, button) in enumerate(self.buttons):
            self._draw_button(screen, fonts, button, i)

        # Right-side field report adds world context without competing with menu.
        rx = int(w * .69)
        report_y = int(h * .62)
        report_w = min(int(w * .25), 310)
        report = pygame.Surface((report_w, int(h * .22)), pygame.SRCALPHA)
        report.fill((4, 10, 10, 115))
        screen.blit(report, (rx, report_y))
        pygame.draw.line(screen, (151, 124, 81), (rx, report_y),
                         (rx + report_w, report_y), 2)
        text(screen, fonts, "SURVIVAL STATUS  /  01",
             rx + 14, report_y + 20, 13, (190, 158, 101), "left", True)
        text(screen, fonts, "SHRINE SECTOR",
             rx + 14, report_y + 54, 22, (218, 207, 170), "left", True)
        text(screen, fonts, "The forest is overrun.",
             rx + 14, report_y + 83, 14, (164, 177, 157), "left")
        text(screen, fonts, "OBJECTIVE: SURVIVE THE WAVES",
             rx + 14, report_y + 106, 11, (190, 145, 103), "left", True)

        text(screen, fonts, "WASD MOVE   /   MOUSE AIM   /   ESC PAUSE",
             int(w * .055), h - 22, 12, (105, 126, 113), "left")
        text(screen, fonts, "v0.9   /   NIGHTFALL", w - 24, h - 22, 12,
             (105, 126, 113), "right")
