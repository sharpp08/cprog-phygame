"""Cinematic post-processing pipeline for WHEN THE WOODS BLEED.

Runs on the game's scene surface after the world (and cached lighting) is
drawn, and before the HUD is blitted to the real screen.  The pipeline is a
NumPy implementation of the same passes defined as GLSL in ``shaders/``
(see ``graphics/shader_manager.py``):

    bloom (low-res glow only) -> color grade -> chromatic aberration
    -> distortion -> vignette -> film grain -> damage / lightning flash

The scene is ALWAYS processed at native resolution so forest, sprites,
particles and UI-adjacent detail stay razor sharp.  The ONLY part of the
pipeline that runs on a downscaled buffer is the bloom glow: bright
pixels are extracted at low resolution, blurred, and upscaled back so the
resulting glow is composited onto the untouched full-resolution frame.

All effect intensities are tweened (exponential smoothing) so events
never cause sudden flashes, and the whole system degrades gracefully:
when disabled (low quality, ``post_fx`` off) the pipeline simply copies
the scene through.

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
        self._gl = None          # optional GpuPostExecutor
        self._tension = 0.0
        self.resize(self.W, self.H, self.quality, self.enabled)

    # ------------------------------------------------------------------
    def attach_gl(self, mgr) -> bool:
        """Attach the ModernGL GPU executor to this pipeline.

        Effect state/tweens stay on this pipeline; only the per-frame
        execution moves to the GPU.  Returns True when the GPU path is
        active (False -> the NumPy reference path keeps being used).
        Never raises.
        """
        if mgr is None or not getattr(mgr, "gl_available", False) \
                or getattr(mgr, "ctx", None) is None:
            return False
        try:
            from graphics.gpu_post import GpuPostExecutor
        except Exception:
            return False
        self._gl = GpuPostExecutor(mgr, self.W, self.H, self.quality)
        if self._gl.failed:
            self._gl = None
        return self._gl is not None

    # ------------------------------------------------------------------
    def resize(self, width: int, height: int,
               quality: Optional[int] = None,
               enabled: Optional[bool] = None) -> None:
        """Rebuild surfaces / cached textures (window or quality change).

        The scene buffer and the final output surface are always created at
        *native* resolution.  Quality only changes how much work each
        effect pass does and the bloom buffer size — it never reduces the
        resolution of the image that reaches the screen.
        """
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
        # Native-resolution output surface: the final frame is ALWAYS the
        # screen size; post-processing never presents a stretched low-res
        # image any more.
        self._out = pygame.Surface((self.W, self.H))
        # ---- bloom: the ONLY low-resolution part of the pipeline ----
        # fx_res scales the bloom glow buffer only: bright-pixel extraction
        # + blur happen there, and the blurred glow is the only thing that
        # gets upscaled (composited back onto the sharp frame).
        res = int(self._specs.get("fx_res", 4))
        self._fxw = max(32, self.W // res)
        self._fxh = max(32, self.H // res)
        self._fx_buf = pygame.Surface((self._fxw, self._fxh))   # bloom src
        self._fx_out = pygame.Surface((self._fxw, self._fxh))   # bloom out
        self._bloom_full = pygame.Surface((self.W, self.H))
        # one blur pass at medium/high, two at ultra
        self._blur_passes = 2 if self.quality >= 3 else 1
        # ---- native-resolution cached masks (rebuilt on resize only) ----
        # Per-pixel effect math stays in uint8 at native resolution: fast
        # on integrated GPUs and it never softens the image.  Float32
        # scratch is used only for event-only passes (distortion /
        # desaturation).
        self._vignette = self._build_vignette()            # f32 mask (H,W)
        self._vig_u8 = (self._vignette * 255.0).astype(np.uint8)
        self._v2d = np.empty((self.H, self.W), dtype=np.uint8)
        self._grain_tiles = [self._grain_tile(i) for i in range(4)]
        self._grain_dev = [(t.astype(np.int16) - 128).astype(np.int8)
                           for t in self._grain_tiles]
        self._mgrid_f = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        self._lut = self._build_lut()
        # reusable native-res buffers
        self._px = np.empty((self.H, self.W, 3), dtype=np.uint8)   # work
        self._gtmp = np.empty((self.H, self.W, 3), dtype=np.uint8)
        self._img = np.zeros((self.H, self.W, 3), dtype=np.float32)
        self._tmp = np.empty((self.H, self.W, 3), dtype=np.float32)
        # keep the GPU executor's buffers in sync
        if self._gl is not None:
            self._gl.resize(self.W, self.H, self.quality)
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
        """Native-resolution vignette mask (0 = no darkening, 1 = max).

        Cached once per resize so the per-frame vignette pass is a single
        uint8 multiply against the full-resolution work frame.
        """
        yy, xx = np.mgrid[0:self.H, 0:self.W]
        nx = (xx - self.W * 0.5) / max(1, self.W * 0.5)
        ny = (yy - self.H * 0.5) / max(1, self.H * 0.5)
        r = np.sqrt(nx * nx + ny * ny)
        mask = np.clip((r - 0.42) / 0.85, 0.0, 1.0) ** 1.8
        return (mask * 0.55).astype(np.float32)   # up to ~55% darkening

    def _grain_tile(self, seed: int) -> np.ndarray:
        """Native-resolution uint8 noise tile (rebuilt on resize only)."""
        rng = np.random.default_rng(1000 + seed)
        return rng.integers(0, 256, size=(self.H, self.W, 3),
                            dtype=np.uint8)

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
        self._tension = tension
        # GPU path: run the same effect state through the GLSL chain at
        # native resolution (the NumPy chain below stays as fallback).
        if self._gl is not None and self._gl.present(
                self.scene, screen, self, offset, self._out):
            return
        s = self._specs
        bloom = float(s.get("bloom", 0.0))
        grade = float(s.get("grade", 0.0))
        vign = float(s.get("vignette", 0.0))
        grain = float(s.get("grain", 0.0))
        chroma = float(s.get("chroma", 0.0))
        distort = float(s.get("distort", 0.0))

        # Native-resolution uint8 work frame.  The scene is NEVER
        # downscaled: every pass below runs on the full-size frame, so the
        # presented image keeps its native pixel detail.  Steady-state
        # passes (grade / vignette / grain / flash) are pure uint8 integer
        # math — cheap on integrated GPUs.  The only low-resolution buffer
        # in the pipeline is the bloom glow extraction.
        src = pygame.surfarray.array3d(self.scene).transpose(1, 0, 2)
        px = self._px
        px[...] = src

        # 1) bloom: extract bright pixels in a SMALL buffer, blur, then
        #    composite the upscaled GLOW onto the sharp native frame.
        if bloom > 0:
            pygame.transform.scale(self.scene, (self._fxw, self._fxh),
                                   self._fx_buf)
            b = pygame.surfarray.array3d(self._fx_buf).transpose(1, 0, 2)
            b = b.astype(np.float32)
            thr = 190.0 - 70.0 * min(1.0, bloom * 1.2)
            bright = np.clip(b - thr, 0.0, 255.0) / 255.0
            for _ in range(self._blur_passes):
                bright = self._box_blur(bright, 3)
            self._fx_out.fill((0, 0, 0))
            pygame.surfarray.blit_array(
                self._fx_out,
                (bright * 255.0).astype(np.uint8).transpose(1, 0, 2))
            pygame.transform.scale(self._fx_out, (self.W, self.H),
                                   self._bloom_full)
            glow = pygame.surfarray.array3d(self._bloom_full) \
                   .transpose(1, 0, 2)
            s8 = int(round(40.0 * min(1.0, bloom * 1.3)))
            # int32 multiply-accumulate avoids uint8 overflow
            p32 = px.astype(np.int32)
            b32 = (glow.astype(np.int32) * s8) // 255
            np.clip(b32, 0, 255, out=b32)
            p32 += b32
            np.clip(p32, 0, 255, out=p32)
            px[...] = p32

        # 2) cinematic color grade (per-channel LUT, full resolution;
        #    the lookup runs on the untouched uint8 source)
        if grade > 0:
            g8 = int(round(grade * 255.0))
            a8 = 255 - g8
            for ch in range(3):
                self._gtmp[..., ch] = self._lut[src[..., ch], ch]
            # int32 to avoid overflow: 255 * 255 = 65025 > int16 max 32767
            p32 = px.astype(np.int32)
            l32 = self._gtmp.astype(np.int32)
            p32 *= a8
            l32 *= g8
            p32 += l32
            p32 //= 255
            np.clip(p32, 0, 255, out=p32)
            px[...] = p32
            # extra desaturation driven by the low-health heartbeat
            ds = self._desat_cur * 0.35
            if ds > 0.01:
                img = self._img
                img[...] = px
                lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
                img *= (1.0 - ds)
                img += lum[..., None] * ds
                np.clip(img, 0.0, 255.0, out=self._tmp)
                px[...] = self._tmp

        # 3) restrained native-resolution detail pass. Sharpening uses a
        #    four-neighbour local average; it never scales or blurs the
        #    source frame and is disabled on low quality.
        detail = float(s.get("detail", 0.0))
        ao = float(s.get("ao", 0.0))
        if detail > 0.0 or ao > 0.0:
            center = px.astype(np.int16)
            local = (np.roll(center, 1, axis=0).astype(np.float32)
                     + np.roll(center, -1, axis=0).astype(np.float32)
                     + np.roll(center, 1, axis=1).astype(np.float32)
                     + np.roll(center, -1, axis=1).astype(np.float32)) * 0.25
            adjusted = center.astype(np.float32)
            if detail > 0.0:
                adjusted += (center - local) * detail
            if ao > 0.0:
                lum_c = (adjusted[..., 0] * 0.299
                         + adjusted[..., 1] * 0.587
                         + adjusted[..., 2] * 0.114)
                lum_n = (local[..., 0] * 0.299
                         + local[..., 1] * 0.587
                         + local[..., 2] * 0.114)
                cavity = np.clip((lum_n - lum_c) * 1.5, 0.0, 30.0) * ao
                adjusted *= (1.0 - cavity[..., None] / 255.0)
            np.clip(adjusted, 0.0, 255.0, out=self._tmp)
            px[...] = self._tmp

        # 4) chromatic aberration: 1-2 px R/B split (kept restrained so
        #    the image stays readable)
        off_r = int(math.ceil(min(2.0, self._ca_cur * chroma * 1.6)))
        if off_r and chroma > 0:
            px[..., 0] = np.roll(px[..., 0], off_r, axis=1)
            px[..., 2] = np.roll(px[..., 2], -off_r, axis=1)
            half = max(1, off_r // 2)
            px[..., 0] = np.roll(px[..., 0], -half, axis=0)
            px[..., 2] = np.roll(px[..., 2], half, axis=0)

        # 4) spatial distortion (heat-warp sine field, event only).
        #    Sub-pixel warps are invisible, so the expensive float32
        #    gather only runs once the effect has actually ramped up.
        dw = self._distort_cur * distort * 1.4
        if dw > 0.12 and distort > 0:
            img = self._img
            img[...] = px
            yy, xx = self._mgrid_f
            ox = np.sin(yy * 0.11 + self._time * 2.1) * dw * 2.0
            oy = np.cos(xx * 0.13 - self._time * 1.7) * dw * 1.5
            ys = np.clip((yy + oy).astype(np.int32), 0, self.H - 1)
            xs = np.clip((xx + ox).astype(np.int32), 0, self.W - 1)
            img = img[ys, xs, :]
            np.clip(img, 0.0, 255.0, out=self._tmp)
            px[...] = self._tmp

        # 5) vignette (cinematic + event boost + low-HP heartbeat),
        #    multiplied against the native-resolution frame
        if vign > 0:
            vi = min(1.0, vign * (0.55 + 0.45 * tension))
            vi += self._vignette_extra * 0.6 + self._vignette_pulse * 0.5
            vi8 = int(min(1.25, vi) * 255.0)
            if vi8:
                # int32 to avoid overflow: 255 * 255 = 65025 > int16 max
                p32 = px.astype(np.int32)
                v32 = (self._vig_u8.astype(np.int32) * vi8) // 255
                np.subtract(255, v32, out=v32)
                p32 *= v32[..., None]
                p32 //= 255
                np.clip(p32, 0, 255, out=p32)
                px[...] = p32

        # 6) film grain: cached native-res tile, integer multiply-add
        if grain > 0:
            ga = grain * (6.0 + 9.0 * tension + 14.0 * self._distort_cur)
            a8 = int(min(255.0, ga * 0.5 / 127.5 * 255.0))
            if a8:
                dev = self._grain_dev[self._grain_tile_i]
                # int32 to avoid overflow: dev range is -128..127, *255
                d32 = dev.astype(np.int32)
                d32 *= a8
                d32 //= 255
                np.clip(d32, -128, 127, out=d32)
                p32 = px.astype(np.int32)
                p32 += d32
                np.clip(p32, 0, 255, out=p32)
                px[...] = p32

        # 7) damage flash / lightning flash
        if self._flash_red > 0.01:
            r8 = int(210.0 * self._flash_red)
            f8 = int(round((1.0 - 0.45 * self._flash_red) * 255.0))
            p32 = px.astype(np.int32)
            p32[..., 0] += r8
            p32[..., 1] *= f8
            p32[..., 1] //= 255
            p32[..., 2] *= f8
            p32[..., 2] //= 255
            np.clip(p32, 0, 255, out=p32)
            px[...] = p32
        if self._flash_white > 0.01:
            fw = self._flash_white
            p32 = px.astype(np.int32)
            p32[..., 0] += int(0.75 * 160.0 * fw)
            p32[..., 1] += int(0.85 * 160.0 * fw)
            p32[..., 2] += int(160.0 * fw)
            np.clip(p32, 0, 255, out=p32)
            px[...] = p32

        # 8) present the NATIVE-RESOLUTION composition
        pygame.surfarray.blit_array(self._out, px.transpose(1, 0, 2))
        screen.blit(self._out, offset)


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

