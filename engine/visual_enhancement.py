"""Cached low-resolution lighting and atmospheric post effects.

This module deliberately stays in Pygame's software-surface pipeline. It
builds expensive radial/vignette textures once, then reuses fixed-size
surfaces so the renderer does not allocate full-screen NumPy arrays every
frame. Quality levels: 0=low, 1=medium, 2=high.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pygame

import config


class VisualEnhancement:
    def __init__(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self._lw = max(1, self.width // 4)
        self._lh = max(1, self.height // 4)
        self._shade = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._shade_full = pygame.Surface((self.width, self.height),
                                          pygame.SRCALPHA)
        self._beam = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._fog = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._fog_full = pygame.Surface((self.width, self.height),
                                        pygame.SRCALPHA)
        # Cheap selective blur: downsample the scene once, then reveal it only
        # outside the player's immediate visibility bubble.
        self._bw = max(1, self.width // 8)
        self._bh = max(1, self.height // 8)
        self._blur_small = pygame.Surface((self._bw, self._bh))
        self._blur_full = pygame.Surface((self.width, self.height),
                                         pygame.SRCALPHA)
        self._blur_mask = pygame.Surface((self._bw, self._bh),
                                         pygame.SRCALPHA)
        self._vignette = self._build_vignette()
        self._grain = self._build_grain()
        self._radials: dict[int, pygame.Surface] = {}
        self._last_size = (self.width, self.height)

    def resize(self, width: int, height: int) -> None:
        size = (max(1, int(width)), max(1, int(height)))
        if size == self._last_size:
            return
        self.__init__(*size)

    def _build_vignette(self) -> pygame.Surface:
        w, h = self.width, self.height
        yy, xx = np.mgrid[0:h, 0:w]
        nx = (xx - w * 0.5) / max(1.0, w * 0.5)
        ny = (yy - h * 0.5) / max(1.0, h * 0.5)
        radius = np.sqrt(nx * nx + ny * ny)
        alpha = np.clip((radius - 0.30) / 0.78, 0.0, 1.0) ** 1.7
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0] = 1
        rgba[..., 1] = 3
        rgba[..., 2] = 9
        rgba[..., 3] = (alpha * 112).astype(np.uint8)
        return pygame.image.frombuffer(rgba.tobytes(), (w, h),
                                       "RGBA").convert_alpha()

    def _build_grain(self) -> pygame.Surface:
        """Build one full-frame, low-opacity grain texture at startup."""
        rng = np.random.default_rng(731)
        w, h = self.width, self.height
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        values = rng.integers(90, 240, size=(h, w), dtype=np.uint8)
        rgba[..., 0] = values
        rgba[..., 1] = values
        rgba[..., 2] = values
        rgba[..., 3] = rng.integers(0, 15, size=(h, w), dtype=np.uint8)
        return pygame.image.frombuffer(rgba.tobytes(), (w, h),
                                       "RGBA").convert_alpha()

    def _radial(self, radius: int) -> pygame.Surface:
        radius = max(8, min(220, int(radius)))
        cached = self._radials.get(radius)
        if cached is not None:
            return cached
        size = radius * 2
        yy, xx = np.mgrid[0:size, 0:size]
        dist = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2)
        falloff = np.clip(1.0 - dist / radius, 0.0, 1.0) ** 1.65
        rgba = np.zeros((size, size, 4), dtype=np.uint8)
        rgba[..., 3] = (falloff * 210).astype(np.uint8)
        radial = pygame.image.frombuffer(rgba.tobytes(), (size, size),
                                         "RGBA").convert_alpha()
        self._radials[radius] = radial
        return radial

    def _apply_dark_edge_blur(self, screen: pygame.Surface, cam,
                              player, quality: int) -> None:
        """Softly defocus only distant, unlit scenery; keep the player area sharp."""
        if player is None:
            return
        # An 1/8-resolution copy gives a restrained optical defocus at low cost.
        pygame.transform.smoothscale(
            screen, (self._bw, self._bh), self._blur_small)
        pygame.transform.smoothscale(
            self._blur_small, (self.width, self.height), self._blur_full)

        sx, sy = cam.iso_to_screen(player.x, player.y, 0.0)
        cx = int(sx * self._bw / self.width)
        cy = int(sy * self._bh / self.height)
        # Keep the full player sprite sharp, not just the feet/pivot.
        # The blur is only allowed to fade in well beyond the character.
        inner = max(8, int(170 * self._bw / self.width))
        outer = max(inner + 8, int(300 * self._bw / self.width))
        max_alpha = (24, 30, 36, 42)[max(0, min(3, int(quality)))]

        self._blur_mask.fill((255, 255, 255, max_alpha))
        # The player-safe center must have ZERO blur opacity. Draw the
        # outer-to-inner circles with decreasing alpha so the mask fades
        # smoothly from the fully sharp inner area to the blurred distance.
        for step in range(12, -1, -1):
            radius = inner + int((outer - inner) * step / 12)
            alpha = int(max_alpha * step / 12.0)
            pygame.draw.circle(self._blur_mask, (255, 255, 255, alpha),
                               (cx, cy), radius)
        self._blur_full.blit(
            self._blur_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(self._blur_full, (0, 0))

    def apply_lighting(self, screen: pygame.Surface, cam, world,
                       player, quality: int,
                       battery: float = 100.0, fog_beam: bool = False,
                       time_value: float = 0.0,
                       extra_lights=()) -> None:
        """Apply cool night ambience and cached radial light falloff.

        ``battery`` drives critical-low flicker; ``fog_beam`` boosts the
        volumetric-style beam so it reads against rain/fog; the beam also
        eases in and out instead of snapping (FLASHLIGHT_SMOOTH).
        ``extra_lights`` are (sx, sy, world_radius, strength) tuples in
        screen space (used for close-enemy glow).
        """
        # Near-total darkness is the baseline. Real dynamic lights below
        # subtract from this darkness mask, revealing only illuminated areas.
        # Quality presets must never make unlit terrain readable again.
        darkness = max(0.0, min(1.0, float(
            getattr(config, "NIGHT_DARKNESS", 0.98))))
        quality_bias = (-2, 0, 2, 2)[max(0, min(3, int(quality)))]
        alpha = max(0, min(252, int(218 + darkness * 32 + quality_bias)))
        self._shade.fill((1, 2, 6, alpha))
        # The distant, unseen world loses detail gradually instead of ending
        # at a harsh black cutoff. The immediate player area stays crisp.
        self._apply_dark_edge_blur(screen, cam, player, quality)
        zoom = max(0.4, float(cam.zoom))
        lights = []
        for i, (wx, wy, radius, intensity) in enumerate(
                getattr(world, "lights", ())):
            sx, sy = cam.iso_to_screen(wx, wy, 0.0)
            # environmental lights breathe very slightly (fire flicker)
            breathe = 0.92 + 0.08 * math.sin(time_value * 4.2 + i * 1.7)
            lights.append((sx / 4.0, sy / 4.0,
                           radius * 32.0 * zoom / 4.0,
                           max(0.0, min(1.0, float(intensity) * breathe))))
        if player is not None:
            # A restrained player halo is always present. With the flashlight
            # off, widen it so nearby terrain remains navigable without
            # revealing the whole forest.
            psx, psy = cam.iso_to_screen(player.x, player.y, 0.0)
            flashlight_on = bool(getattr(player, "flashlight_on", True))
            if flashlight_on:
                ambient_tiles, ambient_strength = 3.5, 0.42
            else:
                ambient_tiles, ambient_strength = 5.4, 0.56
            ambient_radius = ambient_tiles * 32.0 * zoom / 4.0
            lights.append((psx / 4.0, psy / 4.0,
                           ambient_radius, ambient_strength))
        if player is not None and getattr(player, "flashlight_on", True):
            # smooth on/off transition
            target = 1.0
            step = min(1.0, abs(time_value - getattr(
                self, "_last_lt", time_value)) * config
                      .FLASHLIGHT_SMOOTH) if hasattr(config,
                                                      "FLASHLIGHT_SMOOTH") \
                else 0.3
            self._last_lt = time_value
            lvl = getattr(self, "_fl_level", 0.0)
            lvl += (target - lvl) * step
            # critical-battery flicker (never turns the light off itself;
            # the survival system owns forced-off behaviour)
            flick = 1.0
            if battery < config.FLASHLIGHT_LOW_BATTERY:
                sev = 1.0 - battery / config.FLASHLIGHT_LOW_BATTERY
                flick = 1.0 - sev * 0.45 * (
                    0.5 + 0.5 * math.sin(time_value * 11.0)
                    * math.sin(time_value * 3.7 + 1.0))
            lvl *= flick
            self._fl_level = lvl
            sx, sy = cam.iso_to_screen(player.x, player.y, 0.0)
            # Focused flashlight pool: a soft centre and a fast outer falloff.
            # Keep a compact pool around the player's feet; the forward
            # beam does the useful exploration lighting.
            base_r = 5.8 * 32.0 * zoom / 4.0
            base_s = 0.96
            if fog_beam:
                base_r *= 1.1
                base_s = min(1.0, base_s + 0.15)
            lights.append((sx / 4.0, sy / 4.0,
                           base_r * max(0.0, lvl), base_s * max(0.0, lvl)))
            if lvl > 0.03:
                aim_x, aim_y = getattr(player, "aim", (1.0, 0.0))
                dx = (aim_x - aim_y) * config.SCALE_X
                dy = (aim_x + aim_y) * config.SCALE_Y
                length = math.hypot(dx, dy) or 1.0
                dx, dy = dx / length, dy / length
                radius = 10.5 * 32.0 * zoom / 4.0
                ox, oy = sx / 4.0, sy / 4.0
                ex, ey = ox + dx * radius, oy + dy * radius
                px, py = -dy * radius * 0.34, dx * radius * 0.34
                self._beam.fill((0, 0, 0, 0))
                # Stronger center and softer edge reveal terrain without
                # washing out the whole scene.
                b0 = int(132 * lvl * (1.25 if fog_beam else 1.0))
                b1 = int(72 * lvl * (1.25 if fog_beam else 1.0))
                pygame.draw.polygon(
                    self._beam, (0, 0, 0, b0),
                    [(int(ox), int(oy)), (int(ex + px), int(ey + py)),
                     (int(ex - px), int(ey - py))])
                pygame.draw.polygon(
                    self._beam, (0, 0, 0, b1),
                    [(int(ox), int(oy)), (int(ox + dx * radius),
                                          int(oy + dy * radius)),
                     (int(ox + dx * radius * 0.88 + px * 0.55),
                      int(oy + dy * radius * 0.88 + py * 0.55))])
        else:
            self._fl_level = getattr(self, "_fl_level", 0.0) * 0.8
        # close-enemy glow: subtle cool light so pursuers read in the dark
        for sx, sy, wrad, strength in extra_lights:
            lights.append((sx / 4.0, sy / 4.0,
                           wrad * 32.0 * zoom / 4.0,
                           max(0.0, min(1.0, float(strength)))))
        for lx, ly, radius, strength in lights:
            r = max(8, min(220, int(radius)))
            radial = self._radial(r)
            radial.set_alpha(int(255 * strength))
            self._shade.blit(radial, (int(lx - r), int(ly - r)),
                             special_flags=pygame.BLEND_RGBA_SUB)
        if player is not None and getattr(player, "flashlight_on", True):
            self._shade.blit(self._beam, (0, 0),
                             special_flags=pygame.BLEND_RGBA_SUB)
        pygame.transform.scale(self._shade, (self.width, self.height),
                               self._shade_full)
        screen.blit(self._shade_full, (0, 0))
        screen.blit(self._vignette, (0, 0))

    def draw_atmosphere(self, screen: pygame.Surface, cam, world,
                        time_value: float, quality: int,
                        fog_extra: float = 0.0) -> None:
        """Screen-space drifting ground mist (broad, subtle, non-occluding).

        ``fog_extra`` (0..1, from the weather system) thickens the mist
        during rain / fog states so the weather is visible, not just heard.
        """
        if quality < 1:
            return
        self._fog.fill((0, 0, 0, 0))
        # Low, slow-moving ground mist; screen-space puffs are intentionally
        # broad and subtle so they never obscure the player or UI.
        n_puffs = 5 if quality == 1 else 8
        base = (18 + 30 * float(fog_extra)) if quality == 1 else \
            (27 + 22 * float(fog_extra))
        for i in range(n_puffs):
            phase = time_value * (0.10 + i * 0.009) + i * 1.73
            x = int((0.5 + 0.42 * math.sin(phase)) * self._lw)
            y = int((0.58 + 0.25 * math.sin(phase * 0.71 + i)) * self._lh)
            rx = 22 + (i % 3) * 9
            ry = 5 + (i % 2) * 3
            color = (115, 139, 157, min(255, int(base)))
            pygame.draw.ellipse(self._fog, color,
                                (x - rx, y - ry, rx * 2, ry * 2))
            pygame.draw.ellipse(self._fog,
                                (145, 164, 176, min(255, int(base // 2))),
                                (x - rx // 2, y - ry - 2, rx, ry * 2))
        pygame.transform.scale(self._fog, (self.width, self.height),
                               self._fog_full)
        screen.blit(self._fog_full, (0, 0))
        if quality >= 2:
            # Normal alpha blending keeps grain subtle; additive blending
            # turns individual noise pixels into distracting white specks.
            screen.blit(self._grain, (0, 0))
