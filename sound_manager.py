# sound_manager.py - Procedural sound effects using Pygame mixer

import pygame
import array
import math
import random

class SoundManager:
    def __init__(self):
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.enabled = True
            self.shoot_sound = self._create_shoot_sound()
            self.hit_sound = self._create_hit_sound()
            self.zombie_death_sound = self._create_zombie_death_sound()
        except Exception:
            self.enabled = False

    def _create_shoot_sound(self):
        # Generate a short percussive gunshot noise with exponential decay
        sample_rate = 22050
        duration = 0.12  # seconds
        n_samples = int(sample_rate * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / sample_rate
            decay = math.exp(-t * 30.0)
            # Mix white noise and low frequency punch
            noise = random.uniform(-1.0, 1.0)
            wave = math.sin(2 * math.pi * 120.0 * t)
            val = int(decay * (noise * 0.7 + wave * 0.3) * 20000)
            buf.append(max(-32767, min(32767, val)))
        return pygame.mixer.Sound(buffer=buf)

    def _create_hit_sound(self):
        # Generate a dull thud / grunt
        sample_rate = 22050
        duration = 0.15
        n_samples = int(sample_rate * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / sample_rate
            decay = math.exp(-t * 20.0)
            wave = math.sin(2 * math.pi * 80.0 * t)
            val = int(decay * wave * 18000)
            buf.append(max(-32767, min(32767, val)))
        return pygame.mixer.Sound(buffer=buf)

    def _create_zombie_death_sound(self):
        # Generate a squelch / splat
        sample_rate = 22050
        duration = 0.2
        n_samples = int(sample_rate * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / sample_rate
            decay = math.exp(-t * 15.0)
            freq = 200.0 - 150.0 * (i / n_samples)
            wave = math.sin(2 * math.pi * freq * t)
            noise = random.uniform(-0.4, 0.4)
            val = int(decay * (wave + noise) * 16000)
            buf.append(max(-32767, min(32767, val)))
        return pygame.mixer.Sound(buffer=buf)

    def play_shoot(self):
        if self.enabled:
            try:
                self.shoot_sound.play()
            except Exception:
                pass

    def play_hit(self):
        if self.enabled:
            try:
                self.hit_sound.play()
            except Exception:
                pass

    def play_zombie_death(self):
        if self.enabled:
            try:
                self.zombie_death_sound.play()
            except Exception:
                pass
