"""GPU post-processing executor (ModernGL).

Runs the cinematic post chain (bloom glow extraction + fused native-res
composite) on the GPU instead of the NumPy reference path, so the final
image keeps full native pixel detail while staying fast on integrated
graphics.

Architecture
------------
1. The scene surface (rendered by pygame at native resolution) is uploaded
   to a GL texture.
2. Pass A renders the *bloom glow* into a small buffer: bright pixels are
   extracted, thresholded and 9-tap blurred.  This is the ONLY part of the
   pipeline that uses a downscaled buffer.
3. Pass B renders the fused composite (distortion -> chromatic aberration
   -> color grade -> bloom composite -> vignette -> film grain -> flashes)
   at NATIVE resolution into an output FBO.
4. The result is read back once and blitted onto the display surface.

The executor is attached to a :class:`graphics.post_processing.PostPipeline`
(see :meth:`PostPipeline.attach_gl`), which owns all effect state/tweens;
this class only executes the shader chain.  Any runtime failure
permanently disables the GPU path and the NumPy fallback takes over, so the
game always stays playable.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pygame

import moderngl

from graphics import quality_settings
from graphics.shader_manager import ShaderManager


class GpuPostExecutor:
    """Executes the post chain on a live ModernGL context."""

    def __init__(self, mgr: ShaderManager, width: int, height: int,
                 quality: int = 1) -> None:
        self.mgr = mgr
        self.failed = False
        self.last_error = ""
        self.W = width
        self.H = height
        self.quality = quality
        try:
            self._build(width, height, quality)
        except Exception as exc:  # never fatal: NumPy path takes over
            self.failed = True
            self.last_error = str(exc)

    # ------------------------------------------------------------------
    def _build(self, width: int, height: int, quality: int) -> None:
        ctx = self.mgr.ctx
        if ctx is None:
            raise RuntimeError("no live GL context")
        self.ctx = ctx
        self.W = max(32, int(width))
        self.H = max(32, int(height))
        self.quality = quality
        p_bloom = self.mgr.live_program("bloom_extract")
        p_comp = self.mgr.live_program("final_composite")
        if p_bloom is None or p_comp is None:
            raise RuntimeError("required GLSL programs missing")

        # fullscreen triangle strip (shared vertex buffer)
        buf = ctx.buffer(np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0,
                                    1.0, 1.0], dtype="float32").tobytes())
        # Each program needs its own VAO: a VAO is bound to a single
        # program at creation time, and calling vao.render() switches to
        # that program.  Reusing one VAO for both passes would render
        # final_composite into the bloom FBO, which samples the
        # (uninitialised) t_glow texture -> feedback loop of garbage.
        self.vao_bloom = ctx.vertex_array(p_bloom, [(buf, "2f", "a_pos")],
                                          mode=moderngl.TRIANGLE_STRIP)
        self.vao_comp = ctx.vertex_array(p_comp, [(buf, "2f", "a_pos")],
                                         mode=moderngl.TRIANGLE_STRIP)

        res = quality_settings.fx_downscale(quality)
        self.gw = max(32, self.W // res)
        self.gh = max(32, self.H // res)

        # textures + FBOs
        self.scene_tex = ctx.texture((self.W, self.H), 4)
        self.glow_tex = ctx.texture((self.gw, self.gh), 4)
        self.out_tex = ctx.texture((self.W, self.H), 4)
        # Zero-fill the glow buffer so that when bloom strength is 0 the
        # composite pass reads a clean (0,0,0,0) glow instead of garbage
        # from an uninitialised texture.
        self.glow_tex.write(b"\x00" * self.gw * self.gh * 4)
        self.fbo_glow = ctx.framebuffer(color_attachments=self.glow_tex)
        self.fbo_out = ctx.framebuffer(color_attachments=self.out_tex)

        self.p_bloom = p_bloom
        self.p_comp = p_comp

    # ------------------------------------------------------------------
    def set_quality(self, quality: int) -> None:
        """Rebuild the low-res glow buffer for a new quality preset."""
        if quality == self.quality:
            return
        try:
            self._build(self.W, self.H, quality)
            self.failed = False
        except Exception as exc:
            self.failed = True
            self.last_error = str(exc)

    def resize(self, width: int, height: int, quality: int) -> None:
        if width == self.W and height == self.H and quality == self.quality:
            return
        try:
            self._build(width, height, quality)
            self.failed = False
        except Exception as exc:
            self.failed = True
            self.last_error = str(exc)

    # ------------------------------------------------------------------
    def present(self, scene: pygame.Surface, screen: pygame.Surface,
                state, offset: Tuple[int, int],
                out_surface: pygame.Surface) -> bool:
        """Run the GPU chain; blit the native-res result to ``screen``.

        ``state`` is the owning PostPipeline (supplies tweened effect
        values).  Returns False (and disables itself) on any error so the
        NumPy fallback takes over transparently.
        """
        if self.failed:
            return False
        try:
            return self._present(scene, screen, state, offset, out_surface)
        except Exception as exc:
            self.failed = True
            self.last_error = str(exc)
            return False

    def _present(self, scene, screen, state, offset, out_surface) -> bool:
        s = state._specs
        bloom = float(s.get("bloom", 0.0))
        grade = float(s.get("grade", 0.0))
        vign = float(s.get("vignette", 0.0))
        grain = float(s.get("grain", 0.0))
        chroma = float(s.get("chroma", 0.0))
        distort = float(s.get("distort", 0.0))
        tension = state._tension

        # 1) upload the native-res scene (the base image is never softened)
        self.scene_tex.write(pygame.image.tobytes(scene, "RGBA"))

        # ModernGL 5.x: texture uniforms are int (texture unit numbers).
        # Bind textures to fixed units via .use(unit), then set uniforms
        # to those unit numbers.
        self.scene_tex.use(0)   # bind to unit 0
        self.glow_tex.use(1)    # bind to unit 1
        SCENE_UNIT = 0
        GLOW_UNIT = 1

        # 2) bloom glow: the only downscaled buffer in the pipeline
        if bloom > 0:
            self.p_bloom["t_scene"] = SCENE_UNIT
            self.p_bloom["u_res_low"] = (float(self.gw), float(self.gh))
            self.p_bloom["u_threshold"] = (
                190.0 - 70.0 * min(1.0, bloom * 1.2)) / 255.0
            self.fbo_glow.use()
            self.ctx.viewport = (0, 0, self.gw, self.gh)
            self.vao_bloom.render()

        # 3) fused native-resolution composite
        strength = min(1.0, bloom * 1.3) * 40.0 / 255.0
        self.p_comp["t_scene"] = SCENE_UNIT
        self.p_comp["t_glow"] = GLOW_UNIT
        self.p_comp["u_res"] = (float(self.W), float(self.H))
        self.p_comp["u_grade"] = grade
        self.p_comp["u_lowhp"] = min(1.0, state._desat_cur)
        self.p_comp["u_ca"] = min(1.0, state._ca_cur * chroma)
        self.p_comp["u_amount"] = min(1.0, state._distort_cur * distort)
        self.p_comp["u_time"] = float(state._time)
        self.p_comp["u_tension"] = tension
        self.p_comp["u_vignette"] = vign
        self.p_comp["u_pulse"] = state._vignette_pulse
        self.p_comp["u_event"] = state._vignette_extra
        self.p_comp["u_grain"] = grain
        self.p_comp["u_flash_red"] = state._flash_red
        self.p_comp["u_flash_white"] = state._flash_white
        self.p_comp["u_bloom_strength"] = strength
        self.fbo_out.use()
        self.ctx.viewport = (0, 0, self.W, self.H)
        self.vao_comp.render()

        # 4) single native-res readback -> pygame surface -> screen
        data = self.out_tex.read()
        arr = np.frombuffer(data, np.uint8).reshape(self.H, self.W, 4)
        arr3 = np.ascontiguousarray(arr[..., :3].transpose(1, 0, 2))
        pygame.surfarray.blit_array(out_surface, arr3)
        screen.blit(out_surface, offset)
        return True
