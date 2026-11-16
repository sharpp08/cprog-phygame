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
from engine.flashlight import trace_flashlight_beam


class VisualEnhancement:
    def __init__(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self._lw = max(1, self.width // 4)
        self._lh = max(1, self.height // 4)
        self._shade = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._shade_full = pygame.Surface((self.width, self.height),
                                          pygame.SRCALPHA)
        # Broad spill is rendered at quarter resolution then smoothly
        # upscaled; the focused core stays native-resolution and crisp.
        self._beam = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._beam_core = pygame.Surface((self._lw, self._lh), pygame.SRCALPHA)
        self._beam_full = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self._beam_core_full = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        # A second downsample pass feathers rasterized wedges and removes
        # the visible polygon seams without blurring the player or scene.
        self._beam_soft = pygame.Surface((max(1, self.width // 8),
                                          max(1, self.height // 8)), pygame.SRCALPHA)
        self._beam_core_soft = pygame.Surface((max(1, self.width // 8),
                                               max(1, self.height // 8)), pygame.SRCALPHA)
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
        falloff = np.clip(1.0 - dist / radius, 0.0, 1.0) ** 1.9
        rgba = np.zeros((size, size, 4), dtype=np.uint8)
        rgba[..., 3] = (falloff * 210).astype(np.uint8)
        radial = pygame.image.frombuffer(rgba.tobytes(), (size, size),
                                         "RGBA").convert_alpha()
        self._radials[radius] = radial
        return radial

    def _apply_dark_edge_blur(self, screen: pygame.Surface, cam,
                              player, quality: int) -> None:
        """Softly defocus the distant environment while keeping the player sharp."""
        # An 1/8-resolution copy gives an inexpensive optical defocus.
        pygame.transform.smoothscale(
            screen, (self._bw, self._bh), self._blur_small)
        pygame.transform.smoothscale(
            self._blur_small, (self.width, self.height), self._blur_full)

        sx, sy = cam.iso_to_screen(player.x, player.y, 0.0)
        cx = int(sx * self._bw / self.width)
        cy = int(sy * self._bh / self.height)
        # Keep the full player sprite sharp, not just the feet/pivot.
        # The blur is only allowed to fade in well beyond the character.
        # The projected player sprite can be substantially taller than
        # its ground pivot, especially while running or crouching. Protect a
        # generous screen-space radius around the pivot so the blur never
        # washes over the character; only distant scenery is defocused.
        zoom = max(0.4, float(getattr(cam, "zoom", 1.0)))
        inner = max(24, int(240 * zoom * self._bw / self.width))
        outer = max(inner + 12, int(430 * zoom * self._bw / self.width))
        # Blend strongly toward the low-resolution image at long range.
        # The 1/8-resolution copy provides the actual defocus; this alpha
        # controls how clearly that blur reads in the distant environment.
        max_alpha = (145, 165, 185, 200)[max(0, min(3, int(quality)))]

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
        flashlight_enabled = bool(
            getattr(player, "flashlight_on", True)) if player is not None else True
        # Ambient environment brightness is independent of flashlight
        # state. Toggling the flashlight only adds/removes its directional
        # beam; it must not darken or brighten the entire world.
        # Push the unlit environment much closer to black. The radial player
        # light and flashlight beam subtract from this stronger mask, preserving
        # visibility only around nearby light sources.
        # At NIGHT_DARKNESS=0.80 the overlay is approximately 225/255.
        alpha = max(0, min(235, int(205 + darkness * 25 + quality_bias)))
        self._shade.fill((1, 2, 6, alpha))
        # The distant, unseen world loses detail gradually instead of ending
        # at a harsh black cutoff. The immediate player area stays crisp.
        if player is not None and not getattr(player, "flashlight_on", True):
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
        # Keep a soft, blurred pool of visibility around the player. This is
        # deliberately broad and low-intensity; the sharper directional
        # flashlight beam still follows the cursor and does the main lighting.
        if player is not None:
            psx, psy = cam.iso_to_screen(player.x, player.y, 0.0)
            halo_radius = 6.0 * 32.0 * zoom / 4.0
            halo_strength = 0.24
            lights.append((psx / 4.0, psy / 4.0,
                           halo_radius, halo_strength))
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
            if lvl > 0.03:
                aim_x, aim_y = getattr(player, "aim", (1.0, 0.0))
                dx = (aim_x - aim_y) * config.SCALE_X
                dy = (aim_x + aim_y) * config.SCALE_Y
                length = math.hypot(dx, dy) or 1.0
                dx, dy = dx / length, dy / length
                max_range = 40.0
                self._beam.fill((0, 0, 0, 0))
                self._beam_core.fill((0, 0, 0, 0))
                self._beam_full.fill((0, 0, 0, 0))
                self._beam_core_full.fill((0, 0, 0, 0))
                # Trace through the actual tile/obstacle layout. Each ray
                # stops at the first solid object, so trees and rocks cast
                # angular shadows instead of being lit through.
                ray_count = (81, 113, 145, 177)[max(0, min(3, int(quality)))]
                rays = trace_flashlight_beam(
                    world, (player.x, player.y), (aim_x, aim_y),
                    max_range=max_range, ray_count=ray_count,
                    half_spread=0.42)
                ox, oy = sx, sy
                previous = None
                previous_core = None
                fog_gain = 1.18 if fog_beam else 1.0
                center_x, center_y = ox / 4.0, oy / 4.0
                mid_ray = (len(rays) - 1) * 0.5
                for ray_index, (end_x, end_y, energy, _surface) in enumerate(rays):
                    ex, ey = cam.iso_to_screen(end_x, end_y, 0.0)
                    current = (int(ex), int(ey))
                    if previous is not None:
                        strength = max(0.0, min(1.0, energy))
                        # Soft spill is drawn into a smaller buffer; smooth
                        # upscaling feathers the cone boundary instead of
                        # exposing a hard-edged polygon.
                        edge_alpha = int(248 * lvl * strength * fog_gain)
                        if edge_alpha > 0:
                            pygame.draw.polygon(
                                self._beam, (0, 0, 0, edge_alpha),
                                [(int(center_x), int(center_y)),
                                 (int(previous[0] / 4.0), int(previous[1] / 4.0)),
                                 (int(current[0] / 4.0), int(current[1] / 4.0))])
                        # Smooth Gaussian angular falloff avoids the abrupt
                        # cutoff produced by a fixed-width inner fan.
                        angular = (ray_index - mid_ray) / max(1.0, mid_ray)
                        core_profile = math.exp(-5.0 * angular * angular)
                        core_alpha = int(252 * lvl * strength *
                                         core_profile * fog_gain)
                        if core_alpha > 0:
                            pygame.draw.polygon(
                                self._beam_core,
                                (0, 0, 0, core_alpha),
                                [(int(center_x), int(center_y)),
                                 (int(previous[0] / 4.0), int(previous[1] / 4.0)),
                                 (int(current[0] / 4.0), int(current[1] / 4.0))])
                    previous = current
                # Feather both layers through an additional low-resolution
                # pass. The core is no longer rasterized at native resolution,
                # which was the source of the hard inner polygon edge.
                pygame.transform.smoothscale(
                    self._beam, self._beam_soft.get_size(), self._beam_soft)
                pygame.transform.smoothscale(
                    self._beam_soft, (self.width, self.height), self._beam_full)
                pygame.transform.smoothscale(
                    self._beam_core, self._beam_core_soft.get_size(),
                    self._beam_core_soft)
                pygame.transform.smoothscale(
                    self._beam_core_soft, (self.width, self.height),
                    self._beam_core_full)
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
        # Scale ambient lighting before compositing the native-resolution
        # flashlight layers below.
        pygame.transform.scale(self._shade, (self.width, self.height),
                               self._shade_full)
        if player is not None and getattr(player, "flashlight_on", True):
            # Subtract the native-resolution beam after scaling ambient
            # lighting, preserving a crisp, sharply defined light cone.
            self._shade_full.blit(
                self._beam_full, (0, 0),
                special_flags=pygame.BLEND_RGBA_SUB)
            self._shade_full.blit(
                self._beam_core_full, (0, 0),
                special_flags=pygame.BLEND_RGBA_SUB)
        screen.blit(self._shade_full, (0, 0))
        screen.blit(self._vignette, (0, 0))

    def draw_grain(self, screen: pygame.Surface, quality: int) -> None:
        """Apply subtle film grain without generating screen-space mist puffs."""
        if quality >= 2:
            screen.blit(self._grain, (0, 0))
