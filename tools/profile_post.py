"""Profile the PostPipeline hot path.  Run: tools\\profile_post.py"""
import os
import cProfile
import pstats

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
pygame.init()
scr = pygame.display.set_mode((1280, 720))
from graphics.post_processing import PostPipeline
from entities.player import Player

pp = PostPipeline(1280, 720, quality=1)
pp.scene.fill((40, 50, 45))
pl = Player(1, 1)
for _ in range(5):
    pp.update(1 / 60, 0.4)
    pp.present(scr, pl, dt=1 / 60, tension=0.4)

def run():
    for _ in range(20):
        pp.update(1 / 60, 0.4)
        pp.present(scr, pl, dt=1 / 60, tension=0.4)

prof = cProfile.Profile()
prof.enable()
run()
prof.disable()
stats = pstats.Stats(prof)
stats.sort_stats("tottime")
stats.print_stats(18)
