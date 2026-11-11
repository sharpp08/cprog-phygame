"""Display window creation and resolution / fullscreen switching."""
from __future__ import annotations

import pygame


class Window:
    def __init__(self) -> None:
        self.flags = 0
        self.fullscreen = False
        self.res_index = 1
        self.screen = None

    def create(self) -> pygame.Surface:
        import config
        self.res_index = config.DEFAULT_RESOLUTION
        self.fullscreen = config.FULLSCREEN
        self._apply()
        return self.screen

    # ------------------------------------------------------------------
    def set_mode(self, res_index: int, fullscreen: bool) -> None:
        import config
        res_index = max(0, min(len(config.RESOLUTIONS) - 1, res_index))
        self.res_index = res_index
        self.fullscreen = fullscreen
        self._apply()

    def _apply(self) -> None:
        import config
        w, h = config.RESOLUTIONS[self.res_index]
        if self.fullscreen:
            self.flags = pygame.FULLSCREEN
            self.screen = pygame.display.set_mode((w, h), self.flags)
        else:
            self.flags = 0
            self.screen = pygame.display.set_mode((w, h))
        pygame.display.set_caption(config.WINDOW_CAPTION)
