"""Keyboard and mouse input, including isometric-aware aiming."""
from __future__ import annotations

import math
from typing import Tuple

import pygame

import config


class InputManager:
    def __init__(self) -> None:
        self.mouse_down = False
        self.mouse_pressed = False

    # ------------------------------------------------------------------
    def process(self, event) -> None:
        """Update transient edge flags from a single pygame event."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.mouse_down = True
            self.mouse_pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.mouse_down = False

    def end_frame(self) -> None:
        self.mouse_pressed = False

    # ------------------------------------------------------------------
    @staticmethod
    def move_vector() -> Tuple[float, float]:
        k = pygame.key.get_pressed()
        mx = my = 0.0
        if k[pygame.K_a] or k[pygame.K_LEFT]:
            mx -= 1
        if k[pygame.K_d] or k[pygame.K_RIGHT]:
            mx += 1
        if k[pygame.K_w] or k[pygame.K_UP]:
            my -= 1
        if k[pygame.K_s] or k[pygame.K_DOWN]:
            my += 1
        m = math.hypot(mx, my)
        if m > 1e-5:
            mx, my = mx / m, my / m
        return mx, my

    @staticmethod
    def running() -> bool:
        k = pygame.key.get_pressed()
        return bool(k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT])

    @staticmethod
    def pause_pressed() -> bool:
        k = pygame.key.get_pressed()
        return bool(k[pygame.K_ESCAPE] or k[pygame.K_p])

    # ------------------------------------------------------------------
    @staticmethod
    def compute_aim(cam, player) -> Tuple[float, float]:
        """Convert the mouse position to a normalised world-space aim
        direction.  This is the critical isometric correction: screen
        coordinates are mapped back to the ground plane, never used
        directly as a direction.
        """
        mx, my = pygame.mouse.get_pos()
        wx, wy = cam.screen_to_world(mx, my, 0.0)
        dx = wx - player.x
        dy = wy - player.y
        m = math.hypot(dx, dy)
        if m < 1e-5:
            return player.aim
        return dx / m, dy / m
