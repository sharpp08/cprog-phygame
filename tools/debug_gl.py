"""Debug script: inspect GL present result."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy as np, pygame
from entities.player import Player
from graphics.post_processing import PostPipeline
from graphics.shader_manager import build_manager

pygame.init()
screen = pygame.display.set_mode((640, 360))
pl = Player(1, 1)
mgr = build_manager(live=True)
pp = PostPipeline(640, 360, quality=1)
print("attach:", pp.attach_gl(mgr))
pp.scene.fill((20, 24, 20))
pygame.draw.line(pp.scene, (255, 255, 255), (320, 0), (320, 360), 1)
pp.update(1 / 60, tension=0.4)
ok = pp._gl.present(pp.scene, screen, pp, (0, 0), pp._out)
print("gl.present ->", ok, "| failed:", pp._gl.failed,
      "| err:", pp._gl.last_error)

# reproduce with traceback
import traceback
pp._gl.failed = False
try:
    pp._gl._present(pp.scene, screen, pp, (0, 0), pp._out)
    print("manual present OK")
except Exception:
    traceback.print_exc()
out = np.ascontiguousarray(
    pygame.surfarray.array3d(screen).transpose(1, 0, 2))
src = np.ascontiguousarray(
    pygame.surfarray.array3d(pp.scene).transpose(1, 0, 2))
d = np.abs(out.astype(int) - src.astype(int))
print("diff max/mean:", d.max(), round(d.mean(), 2))
# which rows differ
rows = np.where((d.sum(axis=1) > 0).all(axis=0))[0]
print("line col diff top vs bottom:",
      round(d[:20, 320, :].mean(), 2), round(d[-20:, 320, :].mean(), 2))
# check vertical flip: compare out to flipped src
flipped = src[::-1, :, :]
d2 = np.abs(out.astype(int) - flipped.astype(int))
print("if vertically flipped, mean diff would be:", round(d2.mean(), 2))
mgr.release()
