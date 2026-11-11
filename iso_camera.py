# iso_camera.py - Centralized isometric 2.5D camera and projection system

import math
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, MAP_WIDTH, MAP_HEIGHT,
    ISO_SCALE_X, ISO_SCALE_Y, ISO_VOID,
)


class IsoCamera:
    """World-to-screen and screen-to-world isometric projection.

    Gameplay stays in the original top-down world coordinates (x grows right,
    y grows down). The camera projects that plane onto a diamond/iso view:
        screen_x = (wx - wy) * ISO_SCALE_X
        screen_y = (wx + wy) * ISO_SCALE_Y

    The camera offsets the projected origin so the player stays roughly
    centered and clamps the view to keep the playable world on screen.
    """

    def __init__(self):
        self.x = 0.0          # world-space focus point (player)
        self.y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.smoothing = 0.28  # lerp factor per frame (higher = snappier)
        self.offx = 0.0        # pixel offset applied to projected coords
        self.offy = 0.0

        # Cached world->screen offset scale of the map corners so clamping
        # can keep the view inside the projected map bounds.
        self._update_offsets()

    def _update_offsets(self):
        # Project the four map corners to find the projected span of the map.
        corners = [
            self.project_raw(0, 0),
            self.project_raw(MAP_WIDTH, 0),
            self.project_raw(0, MAP_HEIGHT),
            self.project_raw(MAP_WIDTH, MAP_HEIGHT),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        self.map_proj_left = min(xs)
        self.map_proj_right = max(xs)
        self.map_proj_top = min(ys)
        self.map_proj_bottom = max(ys)
        self.map_proj_w = self.map_proj_right - self.map_proj_left
        self.map_proj_h = self.map_proj_bottom - self.map_proj_top

    def project_raw(self, wx, wy):
        """Project world coords to screen coords with no camera offset."""
        sx = (wx - wy) * ISO_SCALE_X
        sy = (wx + wy) * ISO_SCALE_Y
        return sx, sy

    def world_to_screen(self, wx, wy, wz=0.0):
        """Full projection including camera offset. wz raises the point."""
        sx, sy = self.project_raw(wx, wy)
        return sx - self.offx, sy - self.offy - wz

    def screen_to_world(self, sx, sy):
        """Inverse projection: screen pixels back to world coords (wz=0)."""
        px = sx + self.offx
        py = sy + self.offy
        # Solve: px = (wx-wy)*SX, py = (wx+wy)*SY
        wx = (px / ISO_SCALE_X + py / ISO_SCALE_Y) / 2.0
        wy = (py / ISO_SCALE_Y - px / ISO_SCALE_X) / 2.0
        return wx, wy

    def depth(self, wx, wy):
        """Depth key for sorting: larger = drawn later (in front)."""
        return wx + wy

    def set_target(self, wx, wy):
        self.target_x = wx
        self.target_y = wy

    def update(self, player_x, player_y):
        """Smoothly follow the player and clamp to map bounds."""
        self.target_x = player_x
        self.target_y = player_y

        # Smooth follow
        self.x += (self.target_x - self.x) * self.smoothing
        self.y += (self.target_y - self.y) * self.smoothing

        # Center the focus point on screen, then clamp so the map stays in view.
        focus_sx, focus_sy = self.project_raw(self.x, self.y)
        desired_offx = focus_sx - SCREEN_WIDTH / 2.0
        desired_offy = focus_sy - SCREEN_HEIGHT / 2.0

        # Clamp offsets so we never show past the projected map edges when the
        # map is bigger than the screen in projected space.
        min_offx = self.map_proj_left
        max_offx = self.map_proj_right - SCREEN_WIDTH
        min_offy = self.map_proj_top
        max_offy = self.map_proj_bottom - SCREEN_HEIGHT

        if max_offx > min_offx:
            desired_offx = max(min_offx, min(max_offx, desired_offx))
        else:
            desired_offx = (self.map_proj_left + self.map_proj_right) / 2.0 - SCREEN_WIDTH / 2.0

        if max_offy > min_offy:
            desired_offy = max(min_offy, min(max_offy, desired_offy))
        else:
            desired_offy = (self.map_proj_top + self.map_proj_bottom) / 2.0 - SCREEN_HEIGHT / 2.0

        self.offx = desired_offx
        self.offy = desired_offy

    def visible_world_rect(self, padding=300):
        """Approximate world-space rect of what's visible, for culling."""
        # Sample screen corners back to world.
        corners = [
            self.screen_to_world(-padding, -padding),
            self.screen_to_world(SCREEN_WIDTH + padding, -padding),
            self.screen_to_world(-padding, SCREEN_HEIGHT + padding),
            self.screen_to_world(SCREEN_WIDTH + padding, SCREEN_HEIGHT + padding),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return pygame.Rect(
            int(min(xs)), int(min(ys)),
            int(max(xs) - min(xs)), int(max(ys) - min(ys)),
        )
