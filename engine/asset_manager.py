"""Procedural art / asset manager.

Every sprite, tile, shadow and effect in the game is generated in code so the
project is fully self-contained (no external image files to ship).  Surfaces
are built once at startup and cached; the renderer scales them to match the
camera zoom.

The visual language follows the "Isometric Forest Shrine" reference: a dense
autumn forest in golden/orange/green tones around a central clearing with a
small wooden shrine (red tiled roof), a green pond with lily pads, a stone
bridge and a misty waterfall.
"""
from __future__ import annotations

import math
import random
from typing import Dict, Tuple

import pygame

import config


def shade(color: Tuple[int, int, int], f: float) -> Tuple[int, int, int]:
    """Lighten (f>0) or darken (f<0) a colour toward white/black."""
    r, g, b = color
    if f >= 0:
        return (int(r + (255 - r) * f), int(g + (255 - g) * f),
                int(b + (255 - b) * f))
    return (int(r * (1 + f)), int(g * (1 + f)), int(b * (1 + f)))


def lerp_color(a: Tuple[int, int, int], b: Tuple[int, int, int],
               t: float) -> Tuple[int, int, int]:
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


class AssetManager:
    """Holds and generates every cached surface used by the renderer."""

    def __init__(self) -> None:
        self.spr: Dict[str, pygame.Surface] = {}
        self.frames: Dict[str, Dict[str, list]] = {}
        self.variants: Dict[str, list] = {}
        self._zoom_cache: Dict[Tuple[str, float], pygame.Surface] = {}
        self.quality = 1
        self._built = False

    def set_quality(self, q: int) -> None:
        self.quality = int(q)

    # ------------------------------------------------------------------
    def build(self) -> None:
        if self._built:
            return
        random.seed(1234)
        self._make_tiles()
        self._make_lily()
        self._make_environment()
        self._make_character()
        self._make_pickups()
        self._make_fx()
        self._built = True

    # -- lookup ---------------------------------------------------------
    def get(self, name: str) -> pygame.Surface:
        return self.spr[name]

    def variants_list(self, prefix: str) -> list:
        return self.variants.get(prefix, [])

    def scaled(self, name: str, zoom: float) -> pygame.Surface:
        zq = round(zoom, 2)
        base = self.spr[name]
        key = (name, zq)
        if key in self._zoom_cache:
            return self._zoom_cache[key]
        sw, sh = base.get_size()
        if abs(zq - 1.0) < 0.02:
            surf = base
        else:
            surf = pygame.transform.smoothscale(
                base, (max(2, int(sw * zq)), max(2, int(sh * zq))))
        self._zoom_cache[key] = surf
        return surf

    def scaled_variant(self, prefix: str, index: int,
                       zoom: float) -> pygame.Surface:
        lst = self.variants_list(prefix)
        base = lst[index % len(lst)]
        w, h = base.get_size()
        zq = round(zoom, 2)
        key = (prefix, index, zq)
        if key in self._zoom_cache:
            return self._zoom_cache[key]
        if abs(zq - 1.0) < 0.02:
            surf = base
        else:
            surf = pygame.transform.smoothscale(
                base, (max(2, int(w * zq)), max(2, int(h * zq))))
        self._zoom_cache[key] = surf
        return surf

    # -- convenience lookups used by the renderer ---------------------
    def tile(self, name: str, variant: int = 0) -> pygame.Surface:
        if name == "grass":
            return self.spr[self.variants["grass"][variant]]
        return self.spr[name]

    def sprite(self, kind: str, variant: int = 0) -> pygame.Surface:
        if kind in self.variants:
            lst = self.variants[kind]
            return self.spr[lst[variant % len(lst)]]
        return self.spr[kind]

    def player_frames(self, state: str) -> list:
        return self.frames["player"].get(state, self.frames["player"]["idle"])


    # ================================================================
    # tiles
    # ================================================================
    def _diamond(self, W: int, H: int) -> list:
        return [(W / 2, 0), (W, H / 2), (W / 2, H), (0, H / 2)]

    def _iso_block(self, W: int, H: int, depth: int, top, left,
                   right) -> pygame.Surface:
        s = pygame.Surface((W, H + depth), pygame.SRCALPHA)
        pygame.draw.polygon(s, left,
                            [(0, H / 2), (W / 2, H),
                             (W / 2, H + depth), (0, H / 2 + depth)])
        pygame.draw.polygon(s, right,
                            [(W / 2, H), (W, H / 2),
                             (W, H / 2 + depth), (W / 2, H + depth)])
        pygame.draw.polygon(s, top, self._diamond(W, H))
        return s

    def _ground_tile(self, top, speckle=True,
                     speckle_colors=()) -> pygame.Surface:
        """Build a varied diamond tile with details clipped to its surface."""
        W, H = config.TILE_W, config.TILE_H
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        diamond = self._diamond(W, H)
        pygame.draw.polygon(s, top, diamond)
        if speckle and speckle_colors:
            for _ in range(72):
                px = random.randint(5, W - 6)
                py = random.randint(3, H - 4)
                # Keep marks inside the isometric diamond, not in its corners.
                if abs(px - W / 2) / (W / 2) + \
                        abs(py - H / 2) / (H / 2) > 0.82:
                    continue
                col = random.choice(speckle_colors)
                if random.random() < 0.45:
                    pygame.draw.ellipse(s, (*col, 210),
                                        (px, py, 3, 2))
                else:
                    s.set_at((px, py), (*col, 255))
            # Fine, subdued grass blades / mineral streaks.
            for _ in range(7):
                px = random.randint(10, W - 10)
                py = random.randint(5, H - 5)
                if abs(px - W / 2) / (W / 2) + \
                        abs(py - H / 2) / (H / 2) <= 0.78:
                    pygame.draw.line(s, (*random.choice(speckle_colors), 220),
                                     (px, py), (px + 2, py - 2), 1)
        return s

    def _make_tiles(self) -> None:
        cfg = config
        greens = [(86, 118, 58), (92, 110, 52),
                  (104, 108, 50), (120, 110, 54), (138, 120, 58)]
        for i, base in enumerate(greens):
            self.spr[f"grass_{i}"] = self._ground_tile(
                base, speckle_colors=[shade(base, 0.12), shade(base, -0.12),
                                      shade(base, 0.05)])
        self.variants["grass"] = [f"grass_{i}" for i in range(len(greens))]
        self.spr["dirt"] = self._ground_tile(
            (86, 65, 45), speckle_colors=[
                (120, 91, 61), (64, 48, 35), (104, 78, 51)])
        self.spr["path"] = self._ground_tile(
            (112, 105, 91), speckle_colors=[
                (154, 145, 125), (75, 70, 62), (132, 121, 101)])
        self.spr["water"] = self._ground_tile((52, 120, 132), False)
        self.spr["water_edge"] = self._ground_tile((44, 96, 110), False)
        self.spr["rock"] = self._iso_block(
            cfg.TILE_W, cfg.TILE_H, 10,
            (120, 112, 104), shade((120, 112, 104), -0.35),
            shade((120, 112, 104), -0.2))
        self.spr["bridge"] = self._iso_block(
            cfg.TILE_W, cfg.TILE_H, 6,
            (150, 108, 66), shade((150, 108, 66), -0.4),
            shade((150, 108, 66), -0.25))
        self.variants["ground"] = self.variants["grass"] + ["dirt"]
    def _make_lily(self) -> None:
        W, H = config.TILE_W, config.TILE_H
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx, cy = W / 2, H / 2
        for (ox, oy, r) in ((-14, -3, 9), (10, -6, 7), (6, 6, 8)):
            col = (70, 130, 60)
            pygame.draw.ellipse(s, shade(col, -0.35),
                                (cx + ox - r, cy + oy - r * 0.5, r * 2, r))
            pygame.draw.ellipse(s, col,
                                (cx + ox - r + 1, cy + oy - r * 0.5 + 1,
                                 r * 2 - 2, r - 1))
            pygame.draw.line(s, shade(col, -0.4), (cx + ox, cy + oy),
                             (cx + ox + r * 0.9, cy + oy - 3), 1)
        self.spr["lily"] = s

    # ================================================================
    # environment objects (trees, rocks, shrine, waterfall)
    # ================================================================
    def _tree(self, trunk_w: int, trunk_h: int, foliage, base_name: str,
              leaf, height_extra: int = 0):
        """Layered canopy tree with roots, bark grain and leaf highlights."""
        W, H = 104, 104 + height_extra
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx, ground = W / 2, H - 2
        pygame.draw.ellipse(s, (0, 0, 0, 92),
                            (cx - 39, ground - 13, 78, 21))
        # Exposed roots visually tie the trunk into the terrain.
        root = (65, 46, 31)
        pygame.draw.polygon(s, root, [
            (cx - 5, ground - trunk_h * 0.30),
            (cx + 5, ground - trunk_h * 0.30),
            (cx + 22, ground - 2), (cx + 8, ground - 5),
            (cx, ground - 13), (cx - 9, ground - 4),
            (cx - 23, ground - 1)])
        tw, th = max(7, int(trunk_w)), int(trunk_h)
        trunk_top = ground - th
        trunk = (66, 48, 34)
        pygame.draw.polygon(s, trunk, [
            (cx - tw * 0.48, ground), (cx - tw * 0.38, trunk_top),
            (cx + tw * 0.30, trunk_top - 2),
            (cx + tw * 0.50, ground)])
        pygame.draw.polygon(s, (105, 76, 49), [
            (cx - tw * 0.38, ground - 2),
            (cx - tw * 0.25, trunk_top + 2),
            (cx - 1, trunk_top + 1), (cx + 1, ground - 2)])
        for j in range(4):
            bx = cx - tw * 0.25 + j * tw * 0.18
            pygame.draw.line(s, (42, 33, 27),
                             (bx, trunk_top + 8), (bx - 1, ground - 9), 1)
        # Branch forks appear between foliage tiers.
        pygame.draw.line(s, (65, 45, 31),
                         (cx, trunk_top + 13), (cx - 23, trunk_top - 7), 4)
        pygame.draw.line(s, (65, 45, 31),
                         (cx + 1, trunk_top + 17), (cx + 22, trunk_top - 4), 4)
        for i, (dy, rx, ry, f) in enumerate(foliage):
            y = trunk_top - dy + 5
            col = lerp_color(leaf, shade(leaf, 0.28), f)
            rect = (cx - rx, y - ry, rx * 2, ry * 2)
            pygame.draw.ellipse(s, shade(col, -0.42),
                                (cx - rx + 4, y - ry + 7,
                                 rx * 2, ry * 2))
            pygame.draw.ellipse(s, shade(col, -0.12), rect)
            pygame.draw.ellipse(s, col,
                                (cx - rx + 1, y - ry + 1,
                                 rx * 2 - 3, ry * 2 - 4))
            pygame.draw.arc(s, shade(col, 0.42),
                            (cx - rx + 3, y - ry + 2,
                             rx * 2 - 6, ry * 2 - 7), 3.5, 5.8, 2)
            # Small leaf clusters break up the large flat oval silhouettes.
            for _ in range(7):
                lx = random.uniform(cx - rx * 0.72, cx + rx * 0.55)
                ly = random.uniform(y - ry * 0.65, y + ry * 0.42)
                rr = random.randint(2, 4)
                fleck = shade(col, random.uniform(-0.16, 0.24))
                pygame.draw.ellipse(s, fleck,
                                    (int(lx), int(ly), rr * 2, rr))
        self.spr[base_name] = s
        return s

    def _pine_tree(self) -> pygame.Surface:
        s = pygame.Surface((100, 122), pygame.SRCALPHA)
        cx, base = 50, 118
        pygame.draw.ellipse(s, (0, 0, 0, 90), (12, 103, 76, 17))
        pygame.draw.rect(s, (61, 43, 31), (46, 60, 8, 58))
        for i, (top, width, height) in enumerate(
                ((8, 70, 42), (28, 82, 48), (52, 94, 52))):
            pts = [(cx, top), (cx + width // 2, top + height),
                   (cx, top + height - 9), (cx - width // 2, top + height)]
            pygame.draw.polygon(s, (15, 42 + i * 5, 35), pts)
            pygame.draw.polygon(s, (35, 76 + i * 5, 53),
                                [pts[0], pts[1], pts[2]])
            pygame.draw.line(s, (91, 119, 76),
                             (cx - 2, top + 8), (cx - width // 3,
                                                 top + height - 12), 2)
        return s

    def _dead_tree(self, twisted: bool = False) -> pygame.Surface:
        s = pygame.Surface((112, 126), pygame.SRCALPHA)
        cx, base = 56, 122
        pygame.draw.ellipse(s, (0, 0, 0, 88), (15, 108, 82, 17))
        bark = (48, 42, 36)
        points = [(cx - 7, base), (cx - 3, 82), (cx - 10, 54),
                  (cx - 5, 24), (cx + 3, 18), (cx + 4, 57),
                  (cx + 11, 88), (cx + 8, base)]
        pygame.draw.polygon(s, bark, points)
        pygame.draw.line(s, (100, 82, 62), (cx - 2, 111),
                         (cx - 2, 38), 2)
        pygame.draw.line(s, bark, (cx - 4, 63), (cx - 31, 39), 6)
        pygame.draw.line(s, (74, 60, 48), (cx - 31, 39),
                         (cx - 39, 14), 4)
        pygame.draw.line(s, bark, (cx + 5, 70), (cx + 30, 46), 6)
        pygame.draw.line(s, (78, 61, 47), (cx + 30, 46),
                         (cx + 38, 19), 4)
        pygame.draw.line(s, bark, (cx + 1, 39), (cx + 20, 13), 4)
        if twisted:
            pygame.draw.line(s, (86, 65, 48), (cx - 8, 91),
                             (cx + 9, 56), 3)
            pygame.draw.line(s, (86, 65, 48), (cx + 8, 56),
                             (cx - 4, 28), 3)
        for x, y in ((cx - 32, 38), (cx + 31, 45), (cx + 20, 13)):
            pygame.draw.circle(s, (45, 38, 32), (x, y), 3)
        return s

    def _make_environment(self) -> None:
        g = (70, 110, 44)
        o = (180, 120, 40)
        r = (160, 70, 40)
        layers_big = [(6, 26, 20, 1.0), (22, 30, 24, 0.85),
                      (44, 24, 19, 0.55), (60, 16, 13, 0.25)]
        layers_small = [(4, 20, 16, 1.0), (16, 22, 17, 0.6),
                       (30, 15, 12, 0.3)]
        self._tree(14, 34, layers_big, "tree_g", g)
        self._tree(16, 40, layers_big, "tree_o", o, height_extra=6)
        self._tree(12, 26, layers_small, "tree_r", r, height_extra=4)
        self._tree(10, 22, layers_small, "tree_s", g, height_extra=2)
        self.spr["tree_pine"] = self._pine_tree()
        self.spr["tree_dead"] = self._dead_tree()
        self.spr["tree_twisted"] = self._dead_tree(twisted=True)
        self.variants["tree"] = [
            "tree_g", "tree_o", "tree_r", "tree_s",
            "tree_pine", "tree_dead", "tree_twisted"]

        for i, base in enumerate([(110, 104, 96), (90, 86, 82)]):
            s = pygame.Surface((70, 60), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (0, 0, 0, 70), (8, 40, 54, 16))
            pts = [(10, 40), (18, 20), (34, 12), (52, 20), (56, 40),
                   (34, 50)]
            pygame.draw.polygon(s, shade(base, -0.35),
                                [(p[0] + 2, p[1] + 2) for p in pts])
            pygame.draw.polygon(s, base, pts)
            pygame.draw.polygon(s, shade(base, 0.25),
                                [(10, 40), (18, 20), (34, 12),
                                 (34, 42), (34, 50)])
            pygame.draw.line(s, shade(base, 0.4), (18, 20), (30, 18), 1)
            self.spr[f"rock_{i}"] = s
        self.variants["rock"] = ["rock_0", "rock_1"]

        s = pygame.Surface((60, 44), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 60), (10, 30, 40, 12))
        for (ox, oy, rr, f) in ((0, 18, 15, 1.0), (-12, 24, 13, 0.8),
                                 (12, 24, 13, 0.7), (-4, 12, 12, 0.5)):
            col = lerp_color(g, o, f * 0.4)
            pygame.draw.ellipse(s, shade(col, -0.35),
                                (30 + ox - rr + 2, oy - rr * 0.6 + 3,
                                 rr * 2, rr * 1.2))
            pygame.draw.ellipse(s, col,
                                (30 + ox - rr, oy - rr * 0.6, rr * 2,
                                 rr * 1.2))
        self.spr["bush"] = s
        self.spr["shrine"] = self._shrine()
        self.spr["waterfall"] = self._waterfall()
        self.spr["ruin"] = self._ruin()

    def _draw_block(self, s, cx, top, w, d, h, top_c, left_c, right_c):
        half = d / 2
        top_pts = [(cx, top), (cx + w / 2, top + half),
                   (cx, top + d), (cx - w / 2, top + half)]
        left_pts = [(cx - w / 2, top + half), (cx, top + d),
                    (cx, top + d + h), (cx - w / 2, top + half + h)]
        right_pts = [(cx + w / 2, top + half), (cx, top + d),
                     (cx, top + d + h), (cx + w / 2, top + half + h)]
        pygame.draw.polygon(s, left_c, left_pts)
        pygame.draw.polygon(s, right_c, right_pts)
        pygame.draw.polygon(s, top_c, top_pts)
        pygame.draw.polygon(s, shade(top_c, 0.18), top_pts, 1)

    def _shrine(self) -> pygame.Surface:
        W, H = 150, 150
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx = W / 2
        base_y = 118
        self._draw_block(s, cx, base_y, 92, 46, 20,
                         (150, 142, 132), shade((150, 142, 132), -0.35),
                         shade((150, 142, 132), -0.2))
        wall_top = base_y - 46
        body_h = 40
        self._draw_block(s, cx, base_y - 20, 60, 30, body_h,
                         (196, 178, 150), shade((196, 178, 150), -0.4),
                         shade((196, 178, 150), -0.2))
        pygame.draw.rect(s, (70, 48, 34),
                         (cx - 7, wall_top - 2, 14, 22), border_radius=3)
        pygame.draw.rect(s, (50, 34, 24),
                         (cx - 7, wall_top - 2, 14, 22), 1)
        roof_top = wall_top - 30
        ry = wall_top
        roof_c = (150, 44, 40)
        pygame.draw.polygon(s, shade(roof_c, -0.4),
                            [(cx - 40, ry), (cx, ry - 4), (cx, roof_top)])
        pygame.draw.polygon(s, roof_c,
                            [(cx - 40, ry), (cx, roof_top), (cx, ry)])
        pygame.draw.polygon(s, shade(roof_c, 0.25),
                            [(cx, roof_top), (cx, ry), (cx + 40, ry)])
        for k in range(1, 4):
            yy = roof_top + (ry - roof_top) * k / 4.0
            pygame.draw.line(s, shade(roof_c, -0.3),
                            (cx - 40 * k / 4 + 4, yy - 1),
                            (cx + 40 * k / 4 - 4, yy - 1), 1)
        pygame.draw.circle(s, (90, 30, 28), (cx, roof_top), 5)
        for side in (-34, 34):
            lx = cx + side
            pygame.draw.rect(s, (230, 60, 50),
                             (lx - 5, ry + 4, 10, 16), border_radius=3)
            pygame.draw.rect(s, (255, 210, 150),
                             (lx - 2, ry + 7, 4, 10), border_radius=2)
        # Aged roof shingles and weathered timber on the shrine facade.
        for row in range(1, 5):
            yy = roof_top + row * 5
            pygame.draw.line(s, (100, 30, 29),
                             (cx - 34 + row * 2, yy),
                             (cx + 34 - row * 2, yy), 1)
        for side in (-22, 22):
            pygame.draw.line(s, (92, 61, 39),
                             (cx + side, wall_top - 17),
                             (cx + side, base_y - 22), 3)
            pygame.draw.line(s, (220, 194, 160),
                             (cx + side + 2, wall_top - 12),
                             (cx + side + 2, base_y - 28), 1)
        pygame.draw.line(s, (92, 83, 73), (cx - 36, base_y + 8),
                         (cx - 20, base_y + 15), 2)
        pygame.draw.line(s, (92, 83, 73), (cx + 24, base_y + 5),
                         (cx + 34, base_y + 13), 1)
        return s

    def _waterfall(self) -> pygame.Surface:
        W, H = 84, 150
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx = W / 2
        top, bottom = 20, 130
        sheet = (150, 210, 220, 210)
        pygame.draw.polygon(s, sheet,
                            [(cx - 26, top), (cx + 26, top),
                             (cx + 34, bottom), (cx - 34, bottom)])
        for i in range(5):
            xx = cx - 20 + i * 10
            pygame.draw.line(s, (230, 250, 255, 150),
                            (xx, top + 6), (xx - 4, bottom - 4), 2)
            pygame.draw.line(s, (255, 255, 255, 90),
                            (xx + 2, top + 12), (xx - 2, bottom - 8), 1)
        pygame.draw.ellipse(s, (200, 230, 235, 220),
                            (cx - 30, top - 8, 60, 14))
        for (ox, oy, rr) in ((-20, 0, 10), (0, 4, 12), (20, -2, 10),
                             (-8, 8, 8), (10, 8, 8)):
            pygame.draw.ellipse(s, (235, 250, 255, 160),
                                (cx + ox - rr, bottom - 4 + oy - rr * 0.4,
                                 rr * 2, rr))
        return s

    def _ruin(self) -> pygame.Surface:
        W, H = 120, 120
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx, base = 60, 100
        wall = (120, 86, 58)
        # back broken wall
        self._draw_block(s, cx - 14, base - 40, 40, 20, 34,
                         wall, shade(wall, -0.4), shade(wall, -0.22))
        # front partial wall
        self._draw_block(s, cx + 12, base - 12, 32, 16, 20,
                         shade(wall, 0.06), shade(wall, -0.42),
                         shade(wall, -0.24))
        # leaning roof beam
        pygame.draw.line(s, (80, 56, 38), (cx - 26, base - 46),
                         (cx + 20, base - 64), 5)
        pygame.draw.line(s, (96, 68, 44), (cx - 26, base - 45),
                         (cx + 20, base - 63), 2)
        # rubble
        for (ox, oy, sz) in ((-30, -2, 12), (-6, 2, 14), (24, -2, 10),
                             (10, 4, 9)):
            pygame.draw.polygon(s, shade((110, 90, 64), -0.2),
                                [(cx + ox - sz / 2, base - 4 + oy),
                                 (cx + ox + sz / 2, base - 2 + oy),
                                 (cx + ox, base + 4 + oy)])
        return s

    # ================================================================
    # character + zombie animation frames
    # ================================================================
    _PALETTE = {
        "player": dict(skin=(210, 182, 150), top=(96, 112, 140),
                       bot=(64, 66, 74), gun=(58, 60, 66),
                       hair=(60, 44, 34), size=1.0),
        "regular": dict(skin=(150, 150, 96), top=(96, 86, 64),
                       bot=(64, 60, 52), gun=(70, 70, 70),
                       hair=(90, 86, 70), size=1.0),
        "fast": dict(skin=(170, 150, 110), top=(120, 96, 64),
                    bot=(70, 64, 54), gun=(70, 70, 70),
                    hair=(70, 64, 54), size=0.92),
        "tank": dict(skin=(120, 140, 90), top=(70, 80, 54),
                    bot=(54, 54, 50), gun=(50, 50, 50),
                    hair=(60, 66, 52), size=1.3),
        "crawler": dict(skin=(140, 130, 80), top=(85, 78, 58),
                    bot=(58, 54, 46), gun=(60, 60, 60),
                    hair=(78, 70, 56), size=0.85),
        "exploder": dict(skin=(140, 170, 90), top=(90, 100, 58),
                    bot=(62, 58, 50), gun=(55, 55, 55),
                    hair=(70, 82, 52), size=1.05),
    }

    def _humanoid(self, kind: str, pose: str, leg: int = 0,
                  reach: float = 0.0, crouch: float = 0.0,
                  flash: bool = False, phase: float = 0.0,
                  fall: int = 0, gait: float = 1.0):
        """Procedural humanoid frame.

        ``pose`` drives the base stance; ``phase`` (0..1) animates a
        4-frame gait cycle so legs/arms actually swing; ``fall`` orients a
        death pose (0 forward, 1 sideways, 2 backward); ``gait`` stretches
        the swing for asymmetric zombie shambles.
        """
        p = self._PALETTE[kind]
        sc = p["size"]
        W, H = 44, 66
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        cx = W / 2
        skin, top, bot = p["skin"], p["top"], p["bot"]
        gy = 60 - crouch * 6
        pygame.draw.ellipse(s, (0, 0, 0, 80),
                            (cx - 12 * sc, gy - 4, 24 * sc, 9))
        if pose == "dead":
            self._dead_pose(s, kind, sc, gy, fall)
            return s
        if pose == "emerge":
            self._emerge_pose(s, kind, sc, gy, reach, crouch, phase)
            return s

        # Gait phase drives the limb swing.  For a 4-frame cycle the phase
        # is the cycle position (0, 0.25, 0.5, 0.75) and leg alternates.
        amp = 0.5 + 0.5 * abs(gait)
        swing = math.sin(phase * math.pi * 2.0) * amp
        legA_f = swing * 9.0      # front foot offset (px)
        legB_f = -swing * 9.0     # back foot (opposite phase)
        # Body bob: highest mid-stride, lowest at foot contact.
        bob = (abs(swing) if pose in ("walk", "run") else 0.0)
        bob_px = bob * (3.0 if pose == "walk" else 5.0)
        hip_y = gy - 18 * sc - bob_px * 0.5
        shoulder_y = gy - 34 * sc - bob_px
        head_cy = gy - 40 * sc - bob_px
        lean = (6 * reach if pose in ("walk", "run", "idle") else 0.0)
        # Run leans forward more; zombie types hunch.
        lean += 4.0 if pose == "run" else 0.0

        hx, hy = cx - lean * 0.4, hip_y
        # Foot positions: gait offset + pose base
        fA_x = cx - (7 if pose == "walk" else 9) * sc + (legA_f if pose in ("walk", "run") else 0)
        fB_x = cx + (7 if pose == "walk" else 9) * sc + (legB_f if pose in ("walk", "run") else 0)
        fA = (fA_x, gy)
        fB = (fB_x, gy - 2)
        # Arms swing opposite to the same-side leg.
        armA = -swing * 8.0 * (0.8 if pose == "walk" else 1.0)
        armB = swing * 8.0 * (0.8 if pose == "walk" else 1.0)
        pygame.draw.line(s, shade(bot, -0.15), (hx - 2, hy), fA, int(5 * sc))
        pygame.draw.line(s, shade(bot, -0.35), (hx + 2, hy), fB, int(5 * sc))
        ty = shoulder_y + (4 if crouch else 0)
        pygame.draw.polygon(s, shade(top, -0.25),
                            [(hx - 8 * sc, ty + 2), (hx + 8 * sc, ty + 2),
                             (hx + 6 * sc, hip_y), (hx - 6 * sc, hip_y)])
        pygame.draw.polygon(s, top,
                            [(hx - 7 * sc, ty + 1), (hx + 7 * sc, ty + 1),
                             (hx + 5 * sc, hip_y - 2),
                             (hx - 5 * sc, hip_y - 2)])
        pygame.draw.line(s, shade(bot, -0.2),
                         (hx - 6 * sc, hip_y - 3),
                         (hx + 6 * sc, hip_y - 3), 3)
        pygame.draw.ellipse(s, shade(skin, -0.2),
                            (hx - 6 * sc, head_cy - 6 * sc, 12 * sc, 12 * sc))
        pygame.draw.ellipse(s, skin,
                            (hx - 5 * sc, head_cy - 5 * sc, 11 * sc, 11 * sc))
        pygame.draw.ellipse(s, p["hair"],
                            (hx - 5 * sc, head_cy - 6 * sc, 11 * sc, 6 * sc))
        e_col = (240, 90, 60) if pose == "hit" else (30, 24, 20)
        pygame.draw.circle(s, e_col, (int(hx - 2), int(head_cy)), 1)
        pygame.draw.circle(s, e_col, (int(hx + 3), int(head_cy)), 1)
        arm_y = shoulder_y + 6
        reach_px = 16 * reach * sc
        ax, ay = hx + 5 * sc + lean * 0.3, arm_y + armA
        guncol = p["gun"]
        if pose == "shoot":
            pygame.draw.line(s, shade(top, -0.1),
                             (hx + 3 * sc, arm_y),
                             (hx + 4 * sc + reach_px, arm_y - 4), int(4 * sc))
            pygame.draw.line(s, shade(top, -0.3),
                             (hx + 3 * sc, arm_y + 2),
                             (hx + 4 * sc + reach_px, arm_y - 2), int(4 * sc))
            gx, gyw = hx + 4 * sc + reach_px, arm_y - 4
            pygame.draw.rect(s, guncol, (gx, gyw - 2, 12 * sc, 5),
                             border_radius=2)
            pygame.draw.rect(s, shade(guncol, 0.4), (gx + 2, gyw - 3, 5, 2))
            if flash:
                pygame.draw.polygon(s, (255, 230, 150, 220),
                                    [(gx + 12 * sc, gyw - 4),
                                     (gx + 22 * sc, gyw),
                                     (gx + 12 * sc, gyw + 4)])
        elif pose == "reload":
            pygame.draw.line(s, shade(top, -0.1),
                             (hx + 3 * sc, arm_y),
                             (hx + 6 * sc, arm_y + 6), int(4 * sc))
            gx, gyw = hx + 4 * sc, arm_y + 4
            pygame.draw.rect(s, guncol, (gx, gyw, 8 * sc, 5), border_radius=2)
        else:
            arms_ahead = reach > 0.2
            gx = hx + 6 * sc + reach_px
            gyw = arm_y + (2 if arms_ahead else 4) + armA
            pygame.draw.line(s, shade(top, -0.1),
                             (hx + 4 * sc, arm_y), (gx, gyw), int(4 * sc))
            pygame.draw.line(s, shade(top, -0.3),
                             (hx + 4 * sc, arm_y + 2), (gx, gyw + 2),
                             int(4 * sc))
            pygame.draw.rect(s, guncol, (gx, gyw - 2, 9 * sc, 4),
                             border_radius=2)
        # Fine silhouette details make the player and enemy classes easier
        # to read at the game's normal zoom.
        if kind == "player":
            pygame.draw.line(s, shade(top, -0.35),
                             (hx - 5 * sc, ty + 5),
                             (hx - 1 * sc, hip_y - 2), 2)
            pygame.draw.line(s, shade(top, 0.30),
                             (hx + 4 * sc, ty + 6),
                             (hx + 2 * sc, hip_y - 5), 1)
            pygame.draw.line(s, (42, 39, 38),
                             (hx - 6 * sc, hip_y - 5),
                             (hx + 6 * sc, hip_y - 5), 2)
            pygame.draw.rect(s, (104, 83, 57),
                             (hx - 8 * sc, shoulder_y + 5, 5 * sc,
                              9 * sc), border_radius=2)
        else:
            # Torn cloth, dark wounds and dried-blood accents.
            pygame.draw.polygon(s, shade(top, -0.38), [
                (hx - 7 * sc, ty + 8), (hx - 2 * sc, ty + 11),
                (hx - 4 * sc, ty + 16), (hx - 8 * sc, ty + 14)])
            pygame.draw.line(s, (91, 43, 38),
                             (hx + 3 * sc, shoulder_y + 12),
                             (hx + 1 * sc, hip_y - 4), 2)
            pygame.draw.circle(s, (105, 38, 34),
                               (int(hx - 4 * sc), int(shoulder_y + 13)), 2)
            if kind == "tank":
                pygame.draw.line(s, (50, 61, 43),
                                 (hx - 8 * sc, ty + 5),
                                 (hx + 7 * sc, ty + 15), 3)
            elif kind == "fast":
                pygame.draw.line(s, (124, 48, 38),
                                 (hx + 2 * sc, head_cy + 2),
                                 (hx + 6 * sc, head_cy + 5), 2)
        return s

    def _dead_pose(self, s, kind, sc, gy, fall):
        """Lay the body down; ``fall`` orients the collapse direction."""
        p = self._PALETTE[kind]
        cx = 22
        skin, top, bot = p["skin"], p["top"], p["bot"]
        # Ground shadow stretches with the fall.
        shw = 30 + 8 * (fall % 3)
        pygame.draw.ellipse(s, (0, 0, 0, 70),
                            (cx - shw * sc / 2, 48, shw * sc, 12))
        tilt = [-8, 0, 8][fall % 3]
        by = 50
        # Torso laid back
        pygame.draw.polygon(s, shade(top, -0.35),
                            [(cx - 14 * sc + tilt, by),
                             (cx + 12 * sc + tilt, by - 6),
                             (cx + 14 * sc + tilt, by + 6),
                             (cx - 12 * sc + tilt, by + 8)])
        # Legs trailing
        pygame.draw.line(s, shade(bot, -0.4),
                         (cx - 10 * sc, by + 4), (cx - 20 * sc, by + 10 + tilt),
                         int(5 * sc))
        pygame.draw.line(s, shade(bot, -0.5),
                         (cx - 10 * sc, by + 4), (cx - 18 * sc, by + 12 - tilt),
                         int(5 * sc))
        # Head
        pygame.draw.ellipse(s, shade(skin, -0.2),
                            (cx + 8 * sc + tilt, by - 4, 11 * sc, 11 * sc))
        pygame.draw.ellipse(s, skin,
                            (cx + 9 * sc + tilt, by - 3, 9 * sc, 9 * sc))
        # A little blood pool sells the kill.
        pygame.draw.ellipse(s, (90, 20, 18, 150),
                            (cx - 22 * sc, 56, 30 * sc, 8))

    def _emerge_pose(self, s, kind, sc, gy, reach, crouch, phase):
        """Zombie pulling itself up out of the ground (0 = buried, 1 = up)."""
        p = self._PALETTE[kind]
        cx = 22
        skin, top, bot = p["skin"], p["top"], p["bot"]
        rise = phase  # 0..1
        # Dirt mound + roots of the grave.
        pygame.draw.ellipse(s, (60, 45, 30, 200), (cx - 16 * sc, 56, 32 * sc, 12))
        pygame.draw.ellipse(s, (40, 30, 20, 220), (cx - 10 * sc, 58, 20 * sc, 8))
        # Body rises up out of the mound.
        body_top = 52 - rise * 34 * sc
        hip_y = 56 - rise * 20 * sc
        # Torso emerging
        pygame.draw.polygon(s, shade(top, -0.4),
                            [(cx - 7 * sc, body_top),
                             (cx + 7 * sc, body_top),
                             (cx + 5 * sc, hip_y), (cx - 5 * sc, hip_y)])
        # Arms clawing out of the dirt
        for side in (-1, 1):
            ax = cx + side * (9 * sc)
            ay = hip_y - 2
            pygame.draw.line(s, shade(skin, -0.2),
                             (ax, ay), (ax + side * 6, ay + 8), int(4 * sc))
            pygame.draw.line(s, skin,
                             (ax, ay - 2), (ax + side * 4, ay + 4), int(3 * sc))
        # Head breaks the surface last
        if rise > 0.4:
            head_y = body_top - 4
            pygame.draw.ellipse(s, shade(skin, -0.3),
                                (cx - 5 * sc, head_y, 10 * sc, 10 * sc))
            pygame.draw.ellipse(s, skin,
                                (cx - 4 * sc, head_y + 1, 8 * sc, 8 * sc))

    def _make_character(self) -> None:
        frames = self.frames
        # Player: 4-frame walk and run cycles driven by gait phase so the
        # legs alternate naturally and the body bobs.
        pl = {
            "idle": [self._humanoid("player", "idle", phase=k / 4.0)
                     for k in range(4)],
            "walk": [self._humanoid("player", "walk", phase=k / 4.0)
                     for k in range(4)],
            "run": [self._humanoid("player", "run", phase=k / 4.0,
                                   gait=1.4)
                    for k in range(4)],
            "shoot": [self._humanoid("player", "shoot", flash=True)],
            "reload": [self._humanoid("player", "reload", phase=k / 4.0)
                       for k in range(4)],
            "hit": [self._humanoid("player", "hit", reach=0.2, crouch=0.3)],
            "dead": [self._humanoid("player", "dead", fall=k % 3)
                     for k in range(3)],
            "emerge": [self._humanoid("player", "emerge", phase=k / 3.0)
                       for k in range(3)],
        }
        frames["player"] = pl
        for zt in ("regular", "fast", "tank", "crawler", "exploder", "screamer", "armored"):
            # Asymmetric gait per type: fast stumbles, tank drags, crawler low, exploder lurches.
            gait = {"regular": 0.9, "fast": 1.1, "tank": 0.6,
                    "crawler": 0.7, "exploder": 1.0,
                    "screamer": 1.0, "armored": 0.62}.get(zt, 0.9)
            reach = 0.55 if zt != "crawler" else 0.35
            crouch = 0.4 if zt != "crawler" else 0.9
            z = {
                "idle": [self._humanoid(zt, "idle", reach=reach, crouch=crouch,
                                         phase=k / 4.0)
                         for k in range(4)],
                "walk": [self._humanoid(zt, "walk", reach=reach, crouch=crouch,
                                        phase=k / 4.0, gait=gait)
                         for k in range(4)],
                "attack": [self._humanoid(zt, "attack", reach=1.0, crouch=min(0.5, crouch),
                                          phase=k / 4.0)
                           for k in range(4)],
                "hit": [self._humanoid(zt, "hit", reach=reach, crouch=crouch)],
                "dead": [self._humanoid(zt, "dead", fall=k % 3)
                         for k in range(3)],
                "emerge": [self._humanoid(zt, "emerge", reach=reach,
                                          crouch=crouch, phase=k / 3.0)
                           for k in range(3)],
            }
            frames[f"zombie_{zt}"] = z

    # ================================================================
    # pickups
    # ================================================================
    def _make_pickups(self) -> None:
        cfg = config
        for ptype, spec in cfg.PICKUP_TYPES.items():
            s = pygame.Surface((40, 44), pygame.SRCALPHA)
            cx, cy = 20, 26
            col = spec["color"]
            pygame.draw.ellipse(s, (0, 0, 0, 70), (cx - 13, cy + 8, 26, 8))
            if ptype.startswith("ammo"):
                pygame.draw.rect(s, shade(col, -0.4), (cx - 8, cy - 8, 16,
                                                        14), border_radius=2)
                pygame.draw.rect(s, col, (cx - 6, cy - 6, 12, 10),
                                 border_radius=2)
                for i in range(3):
                    pygame.draw.rect(s, shade(col, 0.3),
                                     (cx - 4 + i * 3, cy - 5, 2, 8))
            elif ptype == "battery":
                pygame.draw.rect(s, shade(col, -0.4), (cx - 8, cy - 10, 16, 20), border_radius=3)
                pygame.draw.rect(s, col, (cx - 6, cy - 8, 12, 16), border_radius=2)
                pygame.draw.rect(s, (45, 48, 38), (cx - 3, cy - 12, 6, 3))
                pygame.draw.line(s, (235, 235, 180), (cx, cy - 5), (cx, cy + 5), 2)
            elif ptype == "medkit":
                pygame.draw.rect(s, (240, 240, 235), (cx - 9, cy - 6, 18,
                                                        14),
                                 border_radius=2)
                pygame.draw.rect(s, col, (cx - 2, cy - 5, 4, 12))
                pygame.draw.rect(s, col, (cx - 5, cy - 2, 10, 4))
            else:  # weapon crate
                pygame.draw.rect(s, shade(col, -0.4), (cx - 11, cy - 6, 22,
                                                        16),
                                 border_radius=2)
                pygame.draw.rect(s, col, (cx - 9, cy - 4, 18, 12),
                                 border_radius=2)
                pygame.draw.line(s, shade(col, 0.4), (cx - 8, cy - 2),
                                 (cx + 8, cy + 4), 3)
            self.spr[ptype] = s
        # light beacon for the objective marker
        s = pygame.Surface((24, 60), pygame.SRCALPHA)
        for i, a in enumerate((150, 110, 70)):
            pygame.draw.polygon(s, (255, 220, 120, a),
                                [(12, 0), (3 + i, 40 - i * 2),
                                 (21 - i, 40 - i * 2)])
        pygame.draw.ellipse(s, (255, 230, 150, 220), (4, 46, 16, 8))
        self.spr["beacon"] = s

    # ================================================================
    # effects
    # ================================================================
    def _make_fx(self) -> None:
        # bullet tracer
        s = pygame.Surface((20, 4), pygame.SRCALPHA)
        for x in range(20):
            a = int(255 * (1 - x / 20))
            s.set_at((x, 2), (255, 230, 170, a))
        self.spr["tracer"] = s
        # shotgun pellet
        s = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(s, (240, 210, 140), (3, 3), 3)
        self.spr["pellet"] = s
        # muzzle glow
        s = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 210, 120, 160), (14, 14), 12)
        pygame.draw.circle(s, (255, 250, 200, 220), (14, 14), 6)
        self.spr["muzzle"] = s
        # water ripple ring
        s = pygame.Surface((40, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (220, 240, 255, 90), (4, 8, 32, 16), 2)
        self.spr["ripple"] = s
        # soft light-ray streak (used sparingly, high quality)
        s = pygame.Surface((70, 150), pygame.SRCALPHA)
        for i, a in enumerate((20, 40, 60)):
            w = 6 + i * 3
            pygame.draw.polygon(s, (255, 240, 190, a),
                                [(35 - w, 0), (35 + w, 0),
                                 (35 + 12, 150), (35 - 12, 150)])
        self.spr["ray"] = s
        # fog / mist puff
        s = pygame.Surface((80, 50), pygame.SRCALPHA)
        for (ox, oy, rr) in ((20, 20, 18), (40, 26, 20), (55, 20, 16)):
            pygame.draw.ellipse(s, (210, 220, 230, 40),
                                (ox - rr, oy - rr, rr * 2, rr * 2))
        self.spr["mist"] = s

