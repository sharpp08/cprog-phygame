"""Check the GPU post path end-to-end: sharpness + timing at 720p.

Run: .venv\Scripts\python tools\check_gl_post.py
"""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame
from entities.player import Player
from graphics.post_processing import PostPipeline
from graphics.shader_manager import build_manager

W, H = 1280, 720
pygame.init()
screen = pygame.display.set_mode((W, H))
pl = Player(1.0, 1.0)

mgr = build_manager(live=True)
print("gl_available:", mgr.gl_available, "| errors:", mgr.errors[:2])

pp = PostPipeline(W, H, quality=1)
ok = pp.attach_gl(mgr)
print("attach_gl:", ok)
if not ok:
    raise SystemExit(1)

# sharp test pattern: 1px white vertical lines + checkerboard block
pp.scene.fill((20, 24, 20))
for x in range(0, W, 32):
    pygame.draw.line(pp.scene, (255, 255, 255), (x, 0), (x, H), 1)
pygame.draw.rect(pp.scene, (230, 200, 60), (W // 2 - 40, H // 2 - 40, 80, 80))
ref = np.ascontiguousarray(
    pygame.surfarray.array3d(pp.scene).transpose(1, 0, 2)).copy()

# one warm-up frame
pp.update(1 / 60, tension=0.4)
pp.present(screen, pl, low_hp=False, dt=1 / 60, tension=0.4)

out = np.ascontiguousarray(
    pygame.surfarray.array3d(screen).transpose(1, 0, 2))
diff = np.abs(out.astype(int) - ref.astype(int))
print("out dims:", out.shape, "| scene dims:", ref.shape)
print("max |diff|: %d  mean |diff|: %.2f" % (diff.max(), diff.mean()))
# the 1px lines must survive: sample several line pixels
line_x = 32
col = diff[:, line_x, :].mean()
print("line-col mean diff: %.2f" % col)
assert out.shape == ref.shape, "resolution must be preserved"

# timing
for _ in range(5):
    pp.update(1 / 60, tension=0.4)
    pp.present(screen, pl, dt=1 / 60, tension=0.4)
N = 120
times = []
for _ in range(N):
    t0 = time.perf_counter()
    pp.update(1 / 60, tension=0.4)
    pp.present(screen, pl, dt=1 / 60, tension=0.4)
    times.append(time.perf_counter() - t0)
times.sort()
print("MEDIUM GL 720p: median %.2f ms, p90 %.2f ms"
      % (times[N // 2] * 1000, times[int(N * 0.9)] * 1000))
mgr.release()
