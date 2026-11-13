"""Dynamic forest weather: mist, rain, wind, lightning.

Weather is intentionally slow and atmospheric: it transitions between four
states over tens of seconds, and only the heavy-rain state triggers
lightning + thunder (which the audio manager synthesises).  The renderer
consumes the per-frame values (``rain_amount``, ``wind``,
``fog_density``, ``lightning``) and the audio manager owns the sounds, so
this module stays headless and testable.
"""
from __future__ import annotations

import math
import random
from typing import Optional

import config


class Weather:
    STATES = ("clear", "mist", "light_rain", "heavy_rain")

    def __init__(self, seed: Optional[int] = None) -> None:
        self.rng = random.Random(seed)
        self.state = "clear"
        self.target_state = "clear"
        self._transition_t = 0.0
        self._next_transition = 18.0
        self.wind_dir = 1.0          # screen-space slant direction
        self.wind = 0.15             # 0..1 wind strength
        self.rain_amount = 0.0       # eased 0..1
        self.fog_density = 0.0       # eased 0..1 (extra fog)
        self.lightning = 0.0         # decaying flash intensity 0..1
        self._lightning_timer = 12.0
        self._wind_timer = 0.0
        self._audio = None

    # ------------------------------------------------------------------
    def set_audio(self, audio) -> None:
        self._audio = audio

    # ------------------------------------------------------------------
    def _targets(self, state: str):
        return {
            "clear":  (0.0, 0.0),
            "mist":   (0.0, 0.35),
            "light_rain": (0.45, 0.55),
            "heavy_rain": (1.0, 0.8),
        }[state]

    # ------------------------------------------------------------------
    def update(self, dt: float) -> Optional[str]:
        """Advance weather; return an event name ("lightning") when a
        thunder strike happens this frame, else None."""
        event = None
        # periodic state transitions (slow, non-alarming)
        self._next_transition -= dt
        if self._next_transition <= 0:
            self._next_transition = self.rng.uniform(24.0, 42.0)
            others = [s for s in self.STATES if s != self.target_state]
            # weighted: clear/mist common, rain rarer
            w = {"clear": 4, "mist": 3, "light_rain": 2, "heavy_rain": 1}
            pool = []
            for s in others:
                pool += [s] * w[s]
            self.target_state = self.rng.choice(pool)
        # ease rain / fog toward the target values
        rain_t, fog_t = self._targets(self.target_state)
        k = min(1.0, dt * 0.25)
        self.rain_amount += (rain_t - self.rain_amount) * k
        self.fog_density += (fog_t - self.fog_density) * k
        # wind gusts
        self._wind_timer -= dt
        if self._wind_timer <= 0:
            self._wind_timer = self.rng.uniform(5.0, 11.0)
            self.wind_dir = self.rng.choice((-1.0, 1.0))
            self.wind = min(1.0, self.wind + self.rng.uniform(-0.25, 0.35))
            self.wind = max(0.05, self.wind)
        # lightning (heavy rain only)
        if self.state == "heavy_rain":
            self._lightning_timer -= dt
            if self._lightning_timer <= 0:
                self._lightning_timer = self.rng.uniform(8.0, 18.0)
                self.lightning = 1.0
                event = "lightning"
                if self._audio:
                    self._audio.play("thunder")
        # double-click flash: a strike flickers then fades over ~0.45s
        if self.lightning > 0.0:
            self.lightning = max(0.0, self.lightning - dt * 2.4)
            if self.lightning > 0.55 and self.rng.random() < dt * 4:
                self.lightning = 0.9   # re-flicker
        # settle state name to the reached target when easing is far along
        if abs(self.rain_amount - rain_t) < 0.06 and \
                abs(self.fog_density - fog_t) < 0.06:
            self.state = self.target_state
        return event

    # ------------------------------------------------------------------
    @property
    def is_raining(self) -> bool:
        return self.rain_amount > 0.15

    def rain_intensity(self) -> int:
        """0 = none, 1 = light, 2 = heavy (for particle density)."""
        if self.rain_amount < 0.3:
            return 0
        return 1 if self.rain_amount < 0.75 else 2
