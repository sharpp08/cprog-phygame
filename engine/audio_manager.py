"""Procedural audio manager.

All sound effects and music are synthesised at startup with numpy, so the game
ships without external audio files and never runs out of licensed content.
Volumes are fully adjustable; loops are managed so they never retrigger.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pygame

import config


def _f32_to_sound(arr: np.ndarray, volume: float = 1.0) -> Optional[pygame.mixer.Sound]:
    arr = np.clip(arr * volume, -1.0, 1.0)
    arr = (arr * 32767).astype(np.int16)
    try:
        return pygame.mixer.Sound(buffer=arr.tobytes())
    except Exception:
        return None


class AudioManager:
    def __init__(self) -> None:
        self.sfx: Dict[str, pygame.mixer.Sound] = {}
        self.music: Dict[str, pygame.mixer.Sound] = {}
        self._music_sound: Optional[pygame.mixer.Sound] = None
        self.playing_music: Optional[str] = None
        self.master = config.MASTER_VOL
        self.music_vol = config.MUSIC_VOL
        self.sfx_vol = config.SFX_VOL
        self.rate = 44100
        self._ready = False
        self._rain = None
        self._rain_level = 0.0

    # ------------------------------------------------------------------
    def init(self) -> None:
        try:
            pygame.mixer.init(frequency=self.rate, size=-16, channels=2,
                              buffer=512)
            self._gen_sfx()
            self._gen_music()
            self._ready = True
        except Exception:
            self._ready = False

    # -- synthesis helpers --------------------------------------------
    def _noise(self, n: int) -> np.ndarray:
        return np.random.uniform(-1, 1, n)

    def _decay(self, n: int, k: float) -> np.ndarray:
        return np.exp(-np.arange(n) * k)

    def _lp(self, sig: np.ndarray, alpha: float) -> np.ndarray:
        out = np.empty_like(sig)
        y = 0.0
        for i in range(len(sig)):
            y = y + alpha * (sig[i] - y)
            out[i] = y
        return out

    def _gen_sfx(self) -> None:
        r = self.rate
        for name, (dur, cut, thump) in {
            "shot_pistol": (0.28, 1.4, 110),
            "shot_shotgun": (0.42, 0.8, 90),
            "shot_rifle": (0.22, 1.8, 150),
        }.items():
            n = int(r * dur)
            t = np.arange(n) / r
            burst = self._noise(n) * self._decay(n, 9)
            burst = self._lp(burst, cut / 20)
            tone = np.sin(2 * np.pi * thump * t) * self._decay(n, 18) * 0.6
            sig = burst * 1.4 + tone
            self.sfx[name] = _f32_to_sound(sig / np.max(np.abs(sig)) * 0.9)

        n = int(r * 0.5)
        c1 = self._decay(int(r * 0.12), 40)
        click = np.concatenate([
            self._noise(len(c1)) * c1 * 0.7,
            np.zeros(n // 2),
            self._noise(n // 2) * self._decay(n // 2, 20) * 0.5,
        ])
        click = np.pad(click, (0, n - len(click)))
        self.sfx["reload"] = _f32_to_sound(
            click / max(1, np.max(np.abs(click))))

        n = int(r * 0.18)
        t = np.arange(n) / r
        sig = np.sin(2 * np.pi * 70 * t) * self._decay(n, 22)
        sig += self._lp(self._noise(n), 0.2) * self._decay(n, 30) * 0.4
        self.sfx["footstep"] = _f32_to_sound(
            sig / max(1, np.max(np.abs(sig))) * 0.5)

        n = int(r * 0.9)
        t = np.arange(n) / r
        f0 = 120
        vib = 1 + 0.25 * np.sin(2 * np.pi * 2.4 * t)
        ph = 2 * np.pi * f0 * vib * t
        saw = 2 * (ph / (2 * np.pi) - np.floor(ph / (2 * np.pi) + 0.5))
        sig = np.tanh(saw) * self._decay(n, 2.2) * 0.5
        self.sfx["zombie_groan"] = _f32_to_sound(sig)

        n = int(r * 0.2)
        sig = self._noise(n) * self._decay(n, 18)
        self.sfx["zombie_hit"] = _f32_to_sound(self._lp(sig, 0.4) * 0.8)

        n = int(r * 0.7)
        t = np.arange(n) / r
        f0 = np.linspace(160, 55, n)
        ph = 2 * np.pi * np.cumsum(f0) / r
        self.sfx["zombie_die"] = _f32_to_sound(
            np.sin(ph) * self._decay(n, 3.0) * 0.6)

        # A harsh rising/descending call reserved for the screamer archetype.
        n = int(r * 1.05)
        t = np.arange(n) / r
        sweep = 260.0 + 360.0 * np.sin(np.pi * t / 1.05)
        phase = 2 * np.pi * np.cumsum(sweep) / r
        scream = np.sin(phase) * self._decay(n, 1.1)
        scream += self._lp(self._noise(n), 0.28) * self._decay(n, 2.0) * 0.22
        self.sfx["zombie_scream"] = _f32_to_sound(
            scream / max(1.0, np.max(np.abs(scream))) * 0.85)

        n = int(r * 0.4)
        t = np.arange(n) / r
        sig = (np.sin(2 * np.pi * 880 * t) +
               np.sin(2 * np.pi * 1320 * t) * 0.5) * self._decay(n, 6)
        self.sfx["pickup"] = _f32_to_sound(sig / 2)

        n = int(r * 0.12)
        t = np.arange(n) / r
        self.sfx["ui"] = _f32_to_sound(
            np.sin(2 * np.pi * 660 * t) * self._decay(n, 30) * 0.4)

        # Thunder: a low filtered rumble under a deep 45 Hz thump.
        n = int(r * 1.4)
        t = np.arange(n) / r
        rumble = self._lp(self._noise(n), 0.09) * self._decay(n, 1.6)
        thump = np.sin(2 * np.pi * 45 * t) * self._decay(n, 5.0) * 0.7
        sig = rumble * 0.8 + thump
        self.sfx["thunder"] = _f32_to_sound(
            sig / max(1.0, np.max(np.abs(sig))) * 0.8)

        # Rain: 3-second low-passed noise loop for ambient rainfall.
        n = int(r * 3.0)
        rain = self._lp(self._noise(n), 0.12) * 0.6
        # crossfade the last 5% into the first 5% so the loop is seamless
        fade = int(n * 0.05)
        w = np.linspace(1.0, 0.0, fade)
        rain[-fade:] *= w
        rain[:fade] += rain[n - fade:n] * (1.0 - w) * 0.0
        self._rain = _f32_to_sound(rain / max(1.0, np.max(np.abs(rain))))


    def _gen_music(self) -> None:
        r = self.rate

        def pad(dur, chords, tempo):
            n = int(r * dur)
            out = np.zeros(n)
            step = int(r * tempo)
            for i in range(int(dur / tempo) + 1):
                if i * step >= n:
                    break
                seg = np.arange(min(step, n - i * step)) / r
                for mult, amp in ((1, 0.32), (2.01, 0.16), (3.0, 0.12),
                                  (4.0, 0.06)):
                    f = chords[i % len(chords)] * mult
                    out[i * step:i * step + len(seg)] += \
                        np.sin(2 * np.pi * f * seg) * amp * \
                        np.sin(np.pi * seg / len(seg))
            return out / max(1.0, np.max(np.abs(out)))

        self.music["menu"] = _f32_to_sound(pad(8, [220, 262, 196, 174], 2.0),
                                           self.music_vol)
        self.music["ambient"] = _f32_to_sound(pad(12, [147, 165, 196, 147],
                                                  3.0), self.music_vol)
        self.music["combat"] = _f32_to_sound(pad(6, [98, 98, 110, 82], 1.2),
                                              self.music_vol)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def set_rain(self, level: float) -> None:
        """Loop the synthesized rain ambience at ``level`` (0..1)."""
        if not self._ready or self._rain is None:
            return
        level = max(0.0, min(1.0, level))
        if level <= 0.02 and self._rain_level > 0.0:
            self._rain.stop()
            self._rain_level = 0.0
        elif level > 0.02:
            vol = 0.35 * level * self.sfx_vol * self.master
            if self._rain_level <= 0.0:
                self._rain.set_volume(vol)
                self._rain.play(loops=-1)
            else:
                self._rain.set_volume(vol)
            self._rain_level = level

    def stop_rain(self) -> None:
        if self._rain is not None and self._rain_level > 0.0:
            self._rain.stop()
        self._rain_level = 0.0

    def play(self, name: str) -> None:
        if not self._ready or name not in self.sfx:
            return
        s = self.sfx[name]
        s.set_volume(self.sfx_vol * self.master)
        s.play()

    def play_music(self, name: str, loop: bool = True) -> None:
        if not self._ready or name not in self.music:
            return
        if self.playing_music == name:
            return
        if self._music_sound is not None:
            self._music_sound.stop()
        self.playing_music = name
        self._music_sound = self.music[name]
        self._music_sound.set_volume(self.music_vol * self.master)
        self._music_sound.play(loops=-1 if loop else 0)

    def stop_music(self) -> None:
        if self._music_sound is not None:
            self._music_sound.stop()
            self._music_sound = None
        self.playing_music = None

    def set_volumes(self, master: float, music: float, sfx: float) -> None:
        self.master = master
        self.music_vol = music
        self.sfx_vol = sfx
        if not self._ready:
            return
        for s in self.music.values():
            s.set_volume(music * master)
        for s in self.sfx.values():
            s.set_volume(sfx * master)

