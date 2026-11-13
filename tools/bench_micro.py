"""Microbenchmark of individual post-processing hot spots at 1280x720."""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame
import pygame.pixelcopy

pygame.init()
scr = pygame.display.set_mode((1280, 720))
s = pygame.Surface((1280, 720))
s.fill((40, 50, 45))
px = np.zeros((720, 1280, 3), np.uint8)
a3d = np.zeros((1280, 720, 3), np.uint8)
img = np.zeros((720, 1280, 3), np.float32)
lut = np.tile(np.arange(256, dtype=np.uint8)[:, None], (1, 3))


def t(fn, n=200):
    for _ in range(20):  # warm-up
        fn()
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1000


print("numpy version        :", np.__version__)
print("pixelcopy.s2a u8 (w,h,c): %.2f ms"
      % t(lambda: pygame.pixelcopy.surface_to_array(a3d, s)))
print("surfarray.array3d    : %.2f ms" % t(lambda: pygame.surfarray.array3d(s)))
print("blit_array (native)  : %.2f ms"
      % t(lambda: pygame.surfarray.blit_array(s, px.transpose(1, 0, 2))))
print("transform.scale 1/4  : %.2f ms"
      % t(lambda: pygame.transform.scale(s, (320, 180))))
print("u8  := array3d       : %.2f ms"
      % t(lambda: px.__setitem__(slice(None),
                                  pygame.surfarray.array3d(s).transpose(1, 0, 2))))


def u8_lut_mix():
    np.multiply(px, 100, out=px, casting="unsafe")
    for ch in range(3):
        np.multiply(lut[px[..., ch]], 155, out=lut2, casting="unsafe")
        np.add(px[..., ch], lut2[..., ch], out=lut2,
               casting="unsafe")
    np.floor_divide(px, 255, out=px, casting="unsafe")


lut2 = np.zeros((720, 1280, 3), np.uint8)


print("LUT mix uint8 steps  : %.2f ms" % t(u8_lut_mix))


def vign_pass():
    v = np.empty((720, 1280), dtype=np.uint8)
    vu = np.empty((720, 1280), dtype=np.uint8)
    np.multiply(vu, 150, out=v)
    v //= 255
    np.subtract(255, v, out=v)
    np.multiply(px, v[..., None], out=px, casting="unsafe")


print("vignette uint8 steps : %.2f ms" % t(vign_pass))

