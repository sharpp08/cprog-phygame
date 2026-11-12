"""Cinematic post-processing pipeline for WHEN THE WOODS BLEED.

Runs on the game's scene surface after the world (and cached lighting) is
drawn, and before the HUD is blitted to the real screen.  The pipeline is a
NumPy implementation of the same passes defined as GLSL in ``shaders/``
(see ``graphics/shader_manager.py``):

    bloom -> color grade -> vignette -> film grain -> chromatic aberration
    -> distortion -> damage / lightning flash

All full-screen work happens at a downscaled resolution (``fx_res``) and is
scaled back up once, so the cost is small on integrated GPUs.  Every effect
intensity is tweened (exponential smoothing) so events never cause sudden
flashes, and the whole system degrades gracefully: when disabled (low
quality, ``post_fx`` off) the pipeline simply copies the scene through.

No GL context is required: this module is the reference implementation and
is used when ModernGL is unavailable or the display is headless.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np
import pygame

from graphics import quality_settings


class ScreenShake:
    """Smooth camera shake with exponential decay.

    ``add(magnitude, duration)`` queues a shake; repeated calls within the
    same event ramp up intensity instead of restarting it.  ``offset(dt)``
    returns a pixel (dx, dy) to displace the scene by this frame.
    """

    def __init__(self) -> None:
        self._mag = 0.0
        self._decay = 0.0
        self._t = 0.0
        self._phase = 0.0

    def add(self, magnitude: float, duration: float = 0.4) -> None:
        """Raise the shake intensity (never below the current decay level)."""
        self._mag = max(self._mag, magnitude)
        self._decay = max(self._decay, magnitude / max(0.05, duration))
        self._t = max(self._t, duration)

    def update(self, dt: float) -> None:
        if self._t > 0.0:
            self._t -= dt
            amp = self._mag * math.exp(-self._decay * dt * 6.0)
            self._phase += dt * 47.0
            self._mag = amp
            if self._t <= 0.0 or amp < 0.02:
                self._mag = self._t = 0.0

    def offset(self) -> Tuple[int, int]:
        m = self._mag
        if m < 0.02:
            return (0, 0)
        a = self._phase
        return (int(round(math.sin(a * 1.31) * m)),
                int(round(math.cos(a * 0.97) * m * 0.7)))


class PostPipeline:
    """Owns the scene buffer, effect state and per-frame post chain."""

    def __init__(self, width: int, height: int, quality: int = 1,
                 post_fx: Optional[bool] = None) -> None:
        self.quality = max(0, min(3, int(quality)))
        self._specs = quality_settings.specs_for(self.quality)
        self.W = max(16, int(width))
        self.H = max(16, int(height))
        # explicit override (settings toggle) wins over the preset default
        self.enabled = bool(self._specs["post_fx"] if post_fx is None
                            else post_fx)
        self.resize(self.W, self.H, self.quality, self.enabled)

    # ------------------------------------------------------------------
    def resize(self, width: int, height: int,
               quality: Optional[int] = None,
               enabled: Optional[bool] = None) -> None:
        """Rebuild surfaces / cached textures (window or quality change)."""
        if quality is not None:
            self.quality = max(0, min(3, int(quality)))
            self._specs = quality_settings.specs_for(self.quality)
        if enabled is not None:
            self.enabled = bool(enabled)
        elif "post_fx" in self._specs:
            self.enabled = bool(self._specs["post_fx"])
        self.W = max(16, int(width))
        self.H = max(16, int(height))
        self.scene = pygame.Surface((self.W, self.H))
        res = int(self._specs.get("fx_res", 4))
        self._fxw = max(32, self.W // res)
        self._fxh = max(32, self.H // res)
        self._fx_buf = pygame.Surface((self._fxw, self._fxh))
        self._fx_out = pygame.Surface((self._fxw, self._fxh))
        self._vignette = self._build_vignette()
        self._grain_tiles = [self._grain_tile(i) for i in range(4)]
        # cached 3-channel grain + coordinate grid (avoid per-frame rebuild)
        self._grain_3ch = [np.concatenate([g[..., None]] * 3, axis=2)
                           for g in self._grain_tiles]
        self._mgrid = np.mgrid[0:self._fxh, 0:self._fxw]
        self._lut = self._build_lut()
        # one blur pass at medium/high, two at ultra
        self._blur_passes = 2 if self.quality >= 3 else 1
        # smooth, per-effect intensities (target vs current)
        self._flash_red = 0.0      # damage feedback
        self._flash_white = 0.0    # lightning / supernatural
        self._ca_cur = 0.0
        self._distort_cur = 0.0
        self._desat_cur = 0.0
        self._vignette_extra = 0.0  # horror-event vignette boost
        self._vignette_pulse = 0.0  # low-HP heartbeat
        self._grain_tile_i = 0
        self._time = 0.0


    # -- texture / LUT builders -----------------------------------------
    def _build_vignette(self) -> np.ndarray:
        yy, xx = np.mgrid[0:self._fxh, 0:self._fxw]
        nx = (xx - self._fxw * 0.5) / max(1, self._fxw * 0.5)
        ny = (yy - self._fxh * 0.5) / max(1, self._fxh * 0.5)
        r = np.sqrt(nx * nx + ny * ny)
        mask = np.clip((r - 0.42) / 0.85, 0.0, 1.0) ** 1.8
        return (mask * 0.55).astype(np.float32)   # up to ~55% darkening

    def _grain_tile(self, seed: int) -> np.ndarray:
        rng = np.random.default_rng(1000 + seed)
        tile = rng.integers(0, 255, size=(self._fxh, self._fxw),
                            dtype=np.uint8).astype(np.float32) - 127.5
        return tile * (0.5 / 127.5)          # roughly +/-0.5

    def _build_lut(self) -> np.ndarray:
        """256-entry cinematic grade: cool shadows, warm highlights,
        gently crushed midtones and light desaturation (horror look)."""
        x = np.arange(256, dtype=np.float32)
        t = x / 255.0
        w = (1.0 - t) ** 2
        r = np.clip(x * 1.02 + 2.0 - w * 5.0, 0, 255)  # warm highlights
        g = np.clip(x * 0.98 + 1.0 - w * 2.0, 0, 255)
        b = np.clip(x * 1.05 + 4.0 + w * 6.0, 0, 255)  # cold tint
        out = np.stack([r, g, b], axis=1)
        lum = out @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        out = out * 0.94 + lum[..., None] * 0.06
        return np.round(out).astype(np.uint8)

    # ------------------------------------------------------------------
    # event hooks (called by the game / renderer)
    # ------------------------------------------------------------------
    def on_damage(self, amount: float = 1.0) -> None:
        """Player took a hit: brief red flash + slight chromatic aberration."""
        a = min(1.0, max(0.0, amount))
        self._flash_red = max(self._flash_red, a * 0.55)
        self._ca_cur = max(self._ca_cur, a * 1.2)

    def on_event(self, strength: float = 1.0) -> None:
        """Horror / supernatural event: distortion + grain + vignette spike."""
        s = min(1.0, max(0.0, strength))
        self._distort_cur = max(self._distort_cur, 0.7 * s)
        self._vignette_extra = max(self._vignette_extra, 0.5 * s)
        self._grain_tile_i = (self._grain_tile_i + 1) \
            % len(self._grain_tiles)

    def on_lightning(self, intensity: float = 1.0) -> None:
        self._flash_white = max(self._flash_white,
                                min(0.8, 0.6 * intensity))

    def set_low_health(self, low: bool, dt: float = 0.016) -> None:
        """Smooth heartbeat pulse + desaturation while HP is critical."""
        target = 1.0 if low else 0.0
        self._desat_cur += (target - self._desat_cur) * min(1.0, dt * 1.5)
        if low:
            self._vignette_pulse = 0.30 + 0.35 * abs(math.sin(self._time * 2.6))
        else:
            self._vignette_pulse = 0.0

    # ------------------------------------------------------------------
    # per-frame
    # ------------------------------------------------------------------
    def update(self, dt: float, tension: float = 0.0) -> None:
        """Tween effect intensities toward their resting targets.

        ``tension`` (0..1, from the horror director) adds a subtle resting
        level of chromatic aberration / vignette while the threat is high.
        """
        self._time += dt
        k = min(1.0, dt * 6.0)
        self._flash_red *= max(0.0, 1.0 - dt * 9.0)       # fast decay
        self._flash_white *= max(0.0, 1.0 - dt * 4.5)
        rest_ca = 0.25 * tension * float(self._specs.get("chroma", 0.0))
        rest_dist = 0.15 * tension * float(self._specs.get("distort", 0.0))
        self._ca_cur += (rest_ca - self._ca_cur) * k
        self._ca_cur *= max(0.0, 1.0 - dt * 2.5)
        self._ca_cur = max(self._ca_cur, rest_ca)
        self._distort_cur *= max(0.0, 1.0 - dt * 1.6)
        self._distort_cur = max(self._distort_cur, rest_dist)
        self._vignette_extra *= max(0.0, 1.0 - dt * 0.9)
        if self._grain_tiles and \
                int(self._time / 0.06) % len(self._grain_tiles) != \
                self._grain_tile_i:
            self._grain_tile_i = (self._grain_tile_i + 1) \
                % len(self._grain_tiles)

    # ------------------------------------------------------------------
    def present(self, screen: pygame.Surface,
                player: Optional[object] = None,
                low_hp: bool = False, dt: float = 0.016,
                tension: float = 0.0, offset: Tuple[int, int] = (0, 0)) -> None:
        """Run the post chain on ``self.scene`` and blit to ``screen``.

        The HUD is drawn by the caller *after* this call so post effects
        never touch UI readability.  ``offset`` displaces the whole
        processed frame (camera shake) — the caller pre-fills the screen
        so the exposed edge stays dark.
        """
        if not self.enabled or player is None:
            screen.blit(self.scene, offset)
            return
        self.set_low_health(low_hp, dt)
        s = self._specs
        bloom = float(s.get("bloom", 0.0))
        grade = float(s.get("grade", 0.0))
        vign = float(s.get("vignette", 0.0))
        grain = float(s.get("grain", 0.0))
        chroma = float(s.get("chroma", 0.0))
        distort = float(s.get("distort", 0.0))

        # 1) downscale the scene to effect resolution
        pygame.transform.scale(self.scene, (self._fxw, self._fxh),
                               self._fx_buf)
        arr = pygame.surfarray.array3d(self._fx_buf).transpose(1, 0, 2)
        img = arr.astype(np.float32)

        # 2) bloom: threshold + blur + add
        if bloom > 0:
            thr = 190.0 - 70.0 * min(1.0, bloom * 1.2)
            bright = np.clip(img - thr, 0.0, 255.0) / 255.0
            for _ in range(self._blur_passes):
                bright = self._box_blur(bright, 3)
            img += bright * 40.0 * min(1.0, bloom * 1.3)

        # 3) cinematic color grade (per-channel LUT, strength-scaled mix)
        if grade > 0:
            li = np.clip(img, 0, 255).astype(np.uint8)
            graded = np.empty_like(img)
            for ch in range(3):
                graded[..., ch] = self._lut[li[..., ch], ch]
            img = img * (1.0 - grade) + graded * grade
            # extra desaturation driven by the low-health heartbeat
            ds = self._desat_cur * 0.35
            if ds > 0.01:
                lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
                img = img * (1.0 - ds) + lum[..., None] * ds

        # 4) chromatic aberration: split R/B near the edges
        off_r = int(math.ceil(min(2.0, self._ca_cur * chroma * 1.6)))
        if off_r and chroma > 0:
            img[..., 0] = np.roll(img[..., 0], off_r, axis=1)
            img[..., 2] = np.roll(img[..., 2], -off_r, axis=1)
            half = max(1, off_r // 2)
            img[..., 0] = np.roll(img[..., 0], -half, axis=0)
            img[..., 2] = np.roll(img[..., 2], half, axis=0)

        # 5) spatial distortion (heat-warp style sine field)
        dw = self._distort_cur * distort * 1.4
        if dw > 0.05 and distort > 0:
            yy, xx = self._mgrid
            ox = np.sin(yy * 0.11 + self._time * 2.1) * dw * 2.0
            oy = np.cos(xx * 0.13 - self._time * 1.7) * dw * 1.5
            ys = np.clip((yy + oy).astype(np.int32), 0, self._fxh - 1)
            xs = np.clip((xx + ox).astype(np.int32), 0, self._fxw - 1)
            img = img[ys, xs, :]

        # 6) vignette (cinematic + event boost + low-HP heartbeat)
        if vign > 0:
            vi = min(1.0, vign * (0.55 + 0.45 * tension))
            vi += self._vignette_extra * 0.6 + self._vignette_pulse * 0.5
            vi = min(1.25, vi)
            img *= (1.0 - self._vignette * vi)[..., None]

        # 7) film grain (animated, stronger under tension / events)
        if grain > 0:
            ga = grain * (6.0 + 9.0 * tension + 14.0 * self._distort_cur)
            img += self._grain_3ch[self._grain_tile_i] * ga

        # 8) damage flash / lightning flash
        if self._flash_red > 0.01:
            img[..., 0] = img[..., 0] + 210.0 * self._flash_red
            img[..., 1] = img[..., 1] * (1.0 - 0.45 * self._flash_red)
            img[..., 2] = img[..., 2] * (1.0 - 0.45 * self._flash_red)
        if self._flash_white > 0.01:
            img += (self._flash_white * 160.0) * np.array(
                [0.75, 0.85, 1.0], dtype=np.float32)[None, None, :]

        np.clip(img, 0.0, 255.0, out=img)
        out = img.astype(np.uint8)
        if self._fx_out.get_size() != (self._fxw, self._fxh):
            self._fx_out = pygame.Surface((self._fxw, self._fxh))
        pygame.surfarray.blit_array(self._fx_out, out.transpose(1, 0, 2))
        if self._fx_out.get_size() != screen.get_size():
            # upscale the processed effect buffer back to screen size
            scaled = pygame.transform.scale(self._fx_out, screen.get_size())
            screen.blit(scaled, offset)
        else:
            screen.blit(self._fx_out, offset)


    @staticmethod
    def _box_blur(a: np.ndarray, size: int = 3) -> np.ndarray:
        """Separable box blur on a (h, w, c) float32 volume.

        Vectorised cumulative-sum windows (no Python inner loops).  The
        window wraps at the borders, which is fine for a glow pass on
        the downscaled effect buffer.
        """
        k = size

        def _windows(x: np.ndarray, axis: int) -> np.ndarray:
            """Sum over a sliding window of ``k`` elements along axis.

            Complete windows use the classic cumulative-sum difference
            ``cs[i + k] - cs[i]`` over the zero-prepended cumsum; the
            ``k - 1`` border cells are finished with the actual edge
            values so the blur does not wrap.
            """
            h, w, c = x.shape
            if axis == 1:
                cs = np.cumsum(x, axis=1)
                out = np.zeros((h, w, c), dtype=np.float32)
                # interior: out[j] = cs[j + k - 1] - cs[j - 1]  (j = 1..w-k)
                out[:, 1:w - k + 1] = (cs[:, k:w] - cs[:, :w - k]) / k
                out[:, 0] = x[:, :k].sum(axis=1) / k
                # trailing edge cells (window clipped at the border)
                xp = np.pad(x, ((0, 0), (0, k - 1), (0, 0)), mode="edge")
                for j in range(w - k + 1, w):
                    out[:, j] = xp[:, j:j + k].sum(axis=1) / k
            else:
                cs = np.cumsum(x, axis=0)
                out = np.zeros((h, w, c), dtype=np.float32)
                out[1:h - k + 1] = (cs[k:h] - cs[:h - k]) / k
                out[0] = x[:k].sum(axis=0) / k
                # trailing edge cells (window clipped at the border)
                xp = np.concatenate([x, np.repeat(x[-1:], k - 1, axis=0)],
                                    axis=0)
                for j in range(h - k + 1, h):
                    out[j] = xp[j:j + k].sum(axis=0) / k
            return out

        b = _windows(a, 1)
        return _windows(b, 0)

