"""GLSL shader management with graceful fallback.

``ShaderManager`` locates the ``shaders/`` sources, compiles them through
ModernGL when a GL context is available (it validates every program with a
standalone headless context at startup so a broken shader is caught *before*
any frame is rendered), and exposes per-pass availability.  The NumPy
``PostPipeline`` in :mod:`graphics.post_processing` is the reference
implementation: when ``gl_available`` is False (headless driver, no
ModernGL, or a failed compile) the game simply keeps the CPU pipeline and
stays fully playable.

The GLSL files live under::

    shaders/post_processing/  color_grading, vignette, film_grain,
                              chromatic_aberration, bloom, distortion
    shaders/lighting/         flashlight
    shaders/environment/      fog
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import config

PASS_ORDER: List[str] = [
    "color_grading", "vignette", "film_grain",
    "chromatic_aberration", "bloom", "distortion",
]


@dataclass
class ShaderProgram:
    """A compiled fragment program + its metadata."""
    name: str
    source: str
    gl: object = None            # moderngl.ShaderProgram (GPU path)
    uniforms: Dict[str, str] = field(default_factory=dict)

    def available(self) -> bool:
        return self.gl is not None


class ShaderManager:
    """Loads shaders, compiles when possible, reports availability."""

    def __init__(self, root: Optional[str] = None) -> None:
        self.root = root or config.PROJECT_ROOT
        self.shaders_dir = os.path.join(self.root, "shaders")
        self.programs: Dict[str, ShaderProgram] = {}
        self.gl_available = False
        self.errors: List[str] = []
        self.ctx = None
        self._load_sources()

    # ------------------------------------------------------------------
    def _load_sources(self) -> None:
        for name, path in self._iter_sources():
            try:
                with open(os.path.join(self.shaders_dir, path)) as f:
                    src = f.read()
            except OSError as exc:
                self.errors.append(f"missing shader {path}: {exc}")
                continue
            self.programs[name] = ShaderProgram(name, src)

    @staticmethod
    def _iter_sources():
        layout = {
            "color_grading": "post_processing/color_grading.frag",
            "vignette": "post_processing/vignette.frag",
            "film_grain": "post_processing/film_grain.frag",
            "chromatic_aberration": "post_processing/chromatic_aberration.frag",
            "bloom": "post_processing/bloom.frag",
            "bloom_extract": "post_processing/bloom_extract.frag",
            "final_composite": "post_processing/final_composite.frag",
            "distortion": "post_processing/distortion.frag",
            "fog": "environment/fog.frag",
            "flashlight": "lighting/flashlight.frag",
        }
        for name, rel in layout.items():
            yield name, rel.replace("/", os.sep)

    # ------------------------------------------------------------------
    @property
    def vertex_source(self) -> str:
        path = os.path.join(self.shaders_dir, "fullscreen.vert")
        try:
            with open(path) as f:
                return f.read()
        except OSError:
            return ("attribute vec2 a_pos;\n"
                    "void main(){ gl_Position=vec4(a_pos,0.0,1.0); }")

    def try_compile(self, keep_context: bool = False) -> bool:
        """Compile every program with ModernGL in a standalone context.

        Returns True when all passes compiled (GL path usable).  Failure is
        never fatal: the NumPy fallback keeps working, the errors are kept
        on ``self.errors`` for diagnostics and the programs stay
        source-only.

        ``keep_context=True`` keeps the GL context alive in ``self.ctx``
        so a GPU post-processing executor can render through the compiled
        programs (see :mod:`graphics.gpu_post`).  Call
        :meth:`release` when the game shuts down.
        """
        if not self.programs:
            return False
        try:
            import moderngl
        except ImportError:
            self.errors.append("ModernGL not installed - using NumPy FX")
            return False
        ctx = None
        try:
            ctx = moderngl.create_standalone_context()
        except Exception as exc:  # pragma: no cover - needs a real GPU
            self.errors.append(f"no GL context: {exc}")
            return False
        ok = True
        vert = self.vertex_source
        for name, prog in self.programs.items():
            try:
                prog.gl = ctx.program(
                    vertex_shader=vert,
                    fragment_shader=prog.source,
                )
                # document the uniforms actually present in the program
                try:
                    prog.uniforms = {u.name: str(u.type)
                                     for u in prog.gl.uniforms()
                                     .values()}
                except Exception:
                    prog.uniforms = {}
            except Exception as exc:
                self.errors.append(f"{name}: {exc}")
                ok = False
        if keep_context:
            self.ctx = ctx
        else:
            try:
                ctx.release()
            except Exception:
                pass
        self.gl_available = ok
        return ok

    # ------------------------------------------------------------------
    def release(self) -> None:
        """Free the live GL context (if kept) and its programs."""
        try:
            if self.ctx is not None:
                self.ctx.release()
        except Exception:
            pass
        self.ctx = None
        self.gl_available = False

    def live_program(self, name: str):
        """Compiled program for ``name``, or None when the GL path is off."""
        p = self.programs.get(name)
        if p is None or p.gl is None or self.ctx is None:
            return None
        return p.gl

    # ------------------------------------------------------------------
    def is_pass_available(self, name: str) -> bool:
        """True when the named GPU pass exists and compiled."""
        p = self.programs.get(name)
        return p is not None and p.available()


def build_manager(root: Optional[str] = None, live: bool = False) -> ShaderManager:
    """Create a ShaderManager and attempt GL compilation (never raises).

    With ``live=True`` the compiled context is kept so the GPU post
    executor (:mod:`graphics.gpu_post`) can render with it; with
    ``live=False`` (the default) it is a validation-only compile.
    """
    mgr = ShaderManager(root)
    try:
        mgr.try_compile(keep_context=live)
    except Exception as exc:  # pragma: no cover - defensive
        mgr.errors.append(f"compile crashed: {exc}")
    return mgr
