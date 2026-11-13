"""Ad-hoc benchmark / sanity check for the native-resolution PostPipeline.

Run: .venv\\Scripts\\python tools\\bench_post.py
"""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
import numpy as np
import config
from graphics.post_processing import PostPipeline
from entities.player import Player

pygame.init()
scr = pygame.display.set_mode((320, 180))

for q in range(4):
    pp = PostPipeline(320, 180, quality=q)
    pp.scene.fill((70, 80, 90))
    pygame.draw.rect(pp.scene, (250, 240, 150), (150, 80, 20, 20))
    pl = Player(1.0, 1.0)
    for _ in range(3):
        pp.update(1 / 60, tension=0.5)
        pp.present(scr, pl, low_hp=True, dt=1 / 60, tension=0.5)
    print("q=%d enabled=%s present OK" % (q, pp.enabled))

# step-by-step profile at 720p (ULTRA)
scr = pygame.display.set_mode((1280, 720))
pl = Player(1.0, 1.0)
pp = PostPipeline(1280, 720, quality=3)
pp.scene.fill((40, 50, 45))
N = 30

def t(label, fn, n=N):
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    print("%-28s %8.1f ms" % (label, (time.perf_counter() - t0) / n * 1000))

for quality, label in ((3, "ULTRA"), (2, "HIGH"), (1, "MEDIUM")):
    p2 = PostPipeline(1280, 720, quality=quality)
    p2.scene.fill((40, 50, 45))
    for _ in range(10):  # warm-up
        p2.update(1 / 60, 0.4)
        p2.present(scr, pl, dt=1 / 60, tension=0.4)
    N = 200
    times = []
    for _ in range(N):
        t0 = time.perf_counter()
        p2.update(1 / 60, 0.4)
        p2.present(scr, pl, dt=1 / 60, tension=0.4)
        times.append(time.perf_counter() - t0)
    times.sort()
    print("%s 720p: median %.2f ms, mean %.2f ms, p90 %.2f ms"
          % (label, times[N // 2] * 1000,
             sum(times) / N * 1000, times[int(N * 0.9)] * 1000))