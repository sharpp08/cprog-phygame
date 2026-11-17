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


def main() -> int:
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    pygame.font.init()
    window = Window()
    window.create()
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
