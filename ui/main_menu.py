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
            text(screen, " " if False else fonts, "›", r.right - 22,
                 r.centery - 1, 26, ink, "center", True)
        if hovered:
            pygame.draw.line(screen, (195, 163, 105),
                             (r.x + 14, r.bottom - 3),
                             (r.right - 14, r.bottom - 3), 2)

    def draw(self, screen, fonts: FontSet) -> None:
        w, h = screen.get_size()
        t = pygame.time.get_ticks() * .001
        screen.fill((5, 10, 11))

        # Cold twilight gradient with a warm horizon line.
        for y in range(0, h, 3):
            q = y / max(1, h)
            col = (int(7 + 10*q), int(13 + 12*q), int(18 + 8*q))
            pygame.draw.rect(screen, col, (0, y, w, 3))

        # Distant moon, halo and subtle star field.
        moon = (int(w * .77), int(h * .255))
        halo = pygame.Surface((360, 360), pygame.SRCALPHA)
        for radius, alpha in ((174, 4), (135, 7), (96, 12), (62, 18)):
            pygame.draw.circle(halo, (168, 187, 157, alpha),
                               (180, 180), radius)
        screen.blit(halo, (moon[0] - 180, moon[1] - 180))
        for x, y, speed in self._stars:
            pulse = 105 + int(90 * abs(math.sin(t * speed + x * .03)))
            screen.set_at((x, y), (pulse, pulse, max(0, pulse - 18)))
        pygame.draw.circle(screen, (173, 184, 157), moon, max(20, h // 28))
        pygame.draw.circle(screen, (198, 201, 174), (moon[0] - 5, moon[1] - 6),
                           max(14, h // 38))

        # Three drifting forest layers create depth and parallax.
        for layer, count in ((0, 13), (1, 19), (2, 26)):
            base = int(h * (0.70 + layer * .085))
            color = ((21, 38, 34), (11, 23, 21), (4, 10, 11))[layer]
            for i in range(count):
                seed = i * 97 + layer * 31
                drift = t * (2.2 + layer * 3.0)
                x = int((seed * 43 + drift * (1 if i % 2 else -1)) % (w + 110)) - 55
                tw = 30 + seed % 38
                th = int(h * (.19 + (seed % 17) / 100 + layer * .025))
                pygame.draw.rect(screen, color,
                                 (x - 3, base - th // 3, 6, th // 3 + 5))
                pygame.draw.polygon(screen, color,
                    [(x, base-th), (x-tw//2, base-th//3),
                     (x-tw//4, base-th//3), (x-tw//2, base),
                     (x+tw//2, base), (x+tw//4, base-th//3),
                     (x+tw//2, base-th//3)])

        # Low rolling mist.
        mist = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(5):
            mx = int((t * (8 + i * 3) + i * w * .29) % (w + 440)) - 220
            my = int(h * (.62 + i * .065))
            pygame.draw.ellipse(mist, (145, 163, 143, 12),
                                (mx - 220, my - 24, 440, 76))
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
        text(screen, fonts, "FIELD REPORT  /  01",
             rx + 14, report_y + 20, 13, (190, 158, 101), "left", True)
        text(screen, fonts, "SIGNAL LOST",
             rx + 14, report_y + 54, 24, (205, 133, 100), "left", True)
        text(screen, fonts, "No response beyond the tree line.",
             rx + 14, report_y + 83, 14, (164, 177, 157), "left")
        text(screen, fonts, "Last transmission: 02:17 AM",
             rx + 14, report_y + 106, 12, (119, 139, 122), "left")

        text(screen, fonts, "WASD MOVE   /   MOUSE AIM   /   ESC PAUSE",
             int(w * .055), h - 22, 12, (105, 126, 113), "left")
        text(screen, fonts, "v0.9   /   NIGHTFALL", w - 24, h - 22, 12,
             (105, 126, 113), "right")
