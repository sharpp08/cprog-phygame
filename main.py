"""CPROG PHYGAME - entry point.

Run with:  python main.py
Build a Windows executable with:  pyinstaller main.py
"""
from __future__ import annotations

import os
import sys

import pygame

import config
from engine.game import Game
from engine.window import Window
from ui.loading_screen import LoadingScreen


def main() -> int:
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    pygame.font.init()
    window = Window()
    window.create()
    # Show the forest intro as soon as the window is created, before
    # game systems and graphics assets are initialized.
    loading = LoadingScreen(*window.screen.get_size())
    loading_clock = pygame.time.Clock()
    loading_started = pygame.time.get_ticks()
    loading_duration = 1450
    while pygame.time.get_ticks() - loading_started < loading_duration:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return 0
        elapsed = (pygame.time.get_ticks() - loading_started) / 1000.0
        loading.draw(window.screen, elapsed, "INITIALIZING THE FOREST")
        pygame.display.flip()
        loading_clock.tick(45)

    game = Game(window)
    # Apply saved user preferences loaded by Game before entering the loop.
    game.apply_settings(apply_window=True)
    try:
        game.run()
    except Exception as exc:  # pragma: no cover - top level guard
        import traceback
        traceback.print_exc()
        sys.stderr.write(f"Fatal: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
