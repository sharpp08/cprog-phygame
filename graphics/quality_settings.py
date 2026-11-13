"""Graphics quality presets for WHEN THE WOODS BLEED.

Each preset maps an int quality index (0-3, matching ``config.QUALITY``) to
feature flags used by the renderer, particle system, lighting and the
post-processing pipeline.  Presets are deliberately additive: every level
keeps the game fully playable and only adds cost on top.

``specs_for(quality)`` returns a plain dict so every subsystem can ask for
exactly the flags it needs without importing the whole pipeline.
"""
from __future__ import annotations

from typing import Dict

import config


def _base() -> Dict:
    return {
        # particle / environment density multipliers
        "particles": 0.4,
        "fireflies": False,
        "water_anim": False,
        "mist": False,
        "sway": False,          # tree / foliage wind sway
        # post-processing feature switches (see graphics/post_processing.py)
        "post_fx": False,
        # bloom downscale factor: ONLY the bloom glow buffer is small.
        # Every other effect runs at native resolution so the game image
        # never gets softened; a smaller number = smoother glow (costlier).
        "fx_res": 8,
        "bloom": 0.0,
        "grade": 0.0,
        "vignette": 0.0,
        "grain": 0.0,
        "chroma": 0.0,
        "distort": 0.0,
        "ao": 0.0,             # contact-shadow approximation strength
    }


def specs_for(quality: int) -> Dict:
    """Return the full spec dict for a quality index (0=low .. 3=ultra)."""
    q = max(0, min(3, int(quality)))
    s = _base()
    if q >= 1:  # MEDIUM
        s.update(particles=0.7, fireflies=True, water_anim=True,
                 mist=True, sway=True,
                 post_fx=True, fx_res=6,
                 bloom=0.35, grade=0.7, vignette=0.6, grain=0.25)
    if q >= 2:  # HIGH
        s.update(particles=1.0, fx_res=4,
                 bloom=0.55, grade=0.85, vignette=0.8, grain=0.4,
                 chroma=0.5, distort=0.5, ao=0.6)
    if q >= 3:  # ULTRA
        s.update(particles=1.4, fx_res=3,
                 bloom=0.75, grade=1.0, vignette=1.0, grain=0.5,
                 chroma=0.8, distort=0.8, ao=1.0)
    return s


def enabled(quality: int, key: str) -> bool:
    """Convenience: is a boolean feature enabled at this quality?"""
    return bool(specs_for(quality).get(key, False))


def particle_scale(quality: int) -> float:
    return specs_for(quality)["particles"]


def fx_downscale(quality: int) -> int:
    """Bloom-glow buffer downscale factor (the scene itself is always
    processed and presented at native resolution — see
    :mod:`graphics.post_processing`)."""
    return int(specs_for(quality)["fx_res"])


def quality_index(name: str) -> int:
    """Map a settings-menu name ("low".."ultra") to its index."""
    names = config.QUALITY
    return names.index(name) if name in names else 1
