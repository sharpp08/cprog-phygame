"""Isometric world renderer: ground, water, obstacles, characters, effects,
lighting and fog.  Everything is drawn in screen space through the camera;
world coordinates never leak into the UI layer.
"""
from __future__ import annotations

import math
import random
from typing import Optional, Sequence, Tuple

import pygame

from engine.visual_enhancement import VisualEnhancement
from graphics import quality_settings
from graphics.post_processing import PostPipeline, ScreenShake
from systems.weather import Weather

import config
from engine.collision import distance2


class Renderer:
    def __init__(self, screen, cam, assets, particles, shaders=None) -> None:
        self.screen = screen
        self.cam = cam
        self.assets = assets
        self.particles = particles
        self.W = config.WINDOW_W
        self.H = config.WINDOW_H
        self.quality = 1
        self.time = 0.0
        self.visual = VisualEnhancement(self.W, self.H)
        # graphics upgrade: post pipeline, smooth camera shake and weather
        self.post = PostPipeline(self.W, self.H, self.quality)
        self.shaders = shaders
        if shaders is not None:
            self.post.attach_gl(shaders)
        self.shake = ScreenShake()
        self.weather = Weather(seed=1)
        self._battery = 100.0
        self._last_hp: Optional[float] = None
        self._rain: list = []
        self._splashes: list = []
        self._rain_layer = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._weather_tint = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._lightning_flash = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._lightning_glow = pygame.Surface((112, 64), pygame.SRCALPHA)
        pygame.draw.ellipse(self._lightning_glow, (190, 220, 255, 255),
                            self._lightning_glow.get_rect())
        self._lightning_strike = None   # world-space (x, y), never screen-locked
        self._shadow_cache: dict = {}
        self._scaled_cache: dict = {}
        self._tree_sway_cache: dict = {}
        self._flip_cache: dict = {}
        self._beacon_glow = pygame.Surface((48, 48), pygame.SRCALPHA)
        pygame.draw.circle(self._beacon_glow, (255, 210, 120, 110),
                           (24, 24), 23)
        pygame.draw.circle(self._beacon_glow, (255, 235, 170, 70),
                           (24, 24), 14)
        self._flashes: dict = {}
        self.show_debug = False
        self._fps = 0.0
        self._dbg_font = None
        self._dbg_counts: dict = {}
        self._apply_quality(self.quality)
        self._prep_fog()

    # ------------------------------------------------------------------
    def _apply_quality(self, quality: int) -> None:
        """Propagate a quality level to the post pipeline / particles."""
        self.quality = max(0, min(3, int(quality)))
        self.post.resize(self.W, self.H, quality=self.quality)
        scale = quality_settings.particle_scale(self.quality)
        self.particles.set_max(int(self.particles.MAX_PARTICLES * scale))

    def set_post_fx(self, mode) -> None:
        """Apply the settings' Post-FX toggle: None = follow the quality
        preset, True/False force the pipeline on/off."""
        enabled = None if mode is None else bool(mode)
        self.post.resize(self.W, self.H, quality=self.quality,
                         enabled=enabled)



    # ------------------------------------------------------------------
    def _prep_fog(self) -> None:
        """Resize cached atmosphere / post surfaces after a display
        mode change."""
        self.visual.resize(self.W, self.H)
        self.post.resize(self.W, self.H, quality=self.quality)
        self._rain_layer = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._weather_tint = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self._lightning_flash = pygame.Surface((self.W, self.H), pygame.SRCALPHA)

    def _scale_sprite(self, spr: pygame.Surface, zoom=None):
        """Return a cached sprite scaled to the current isometric camera zoom."""
        factor = self.cam.zoom if zoom is None else float(zoom)
        zq = round(factor, 2)
        if abs(zq - 1.0) < 0.02:
            return spr
        key = (id(spr), zq)
        scaled = self._scaled_cache.get(key)
        if scaled is None:
            scaled = pygame.transform.smoothscale(
                spr, (max(2, int(spr.get_width() * zq)),
                      max(2, int(spr.get_height() * zq))))
            self._scaled_cache[key] = scaled
        return scaled

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _cull_bounds(self) -> Tuple[int, int, int, int]:
        cam = self.cam
        pts = [cam.screen_to_world(x, y, 0.0) for (x, y) in
               ((0, 0), (self.W, 0), (0, self.H), (self.W, self.H))]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        pad = 2
        minx = int(math.floor(min(xs))) - pad
        miny = int(math.floor(min(ys))) - pad
        maxx = int(math.ceil(max(xs))) + pad
        maxy = int(math.ceil(max(ys))) + pad
        minx = max(0, minx)
        miny = max(0, miny)
        return minx, miny, maxx, maxy

    # ------------------------------------------------------------------
    def draw_world(self, world, player, zombies: Sequence, pickups: Sequence,
                   bullets: Sequence, grenades: Sequence = ()) -> None:
        cam = self.cam
        bounds = self._cull_bounds()
        minx, miny, maxx, maxy = bounds
        # Cull static obstacles exactly once per frame. The same visible list
        # feeds depth sorting and diagnostics instead of scanning the full map
        # repeatedly.
        visible_obstacles = world.cull_obstacles(
            minx, miny, maxx, maxy, pad=0.0)
        self._draw_ground(world, minx, miny, maxx, maxy)
        self._draw_water(world, minx, miny, maxx, maxy)
        items = self._depth_items(
            world, player, zombies, pickups,
            visible_obstacles=visible_obstacles)
        for it in items:
            self._draw_item(it)
        self._draw_bullets(bullets)
        self._draw_grenades(grenades)
        self._draw_particles()
        self._apply_lighting(world, player, zombies)
        self.visual.draw_grain(self.screen, self.quality)
        # Debug-only counters and camera projections are skipped during
        # normal play to avoid per-frame allocations and extra transforms.
        if self.show_debug:
            cam_x, cam_y = cam.fx, cam.fy
            psx, psy = (
                cam.iso_to_screen(player.x, player.y, 0.0)
                if player is not None else (0.0, 0.0)
            )
            self._dbg_counts = {
                "tiles_total": world.W * world.H,
                "obstacles_total": len(world.obstacles),
                "obstacles_visible": len(visible_obstacles),
                "depth_items": len(items),
                "drawn_items": len(items),
                "zombies": len(zombies),
                "pickups": len(pickups),
                "bullets": len(bullets),
                "cam_x": cam_x,
                "cam_y": cam_y,
                "cam_zoom": cam.zoom,
                "player_x": player.x if player else 0.0,
                "player_y": player.y if player else 0.0,
                "player_sx": psx,
                "player_sy": psy,
            }

    # ------------------------------------------------------------------
    def _draw_ground(self, world, minx, miny, maxx, maxy) -> None:
        cam = self.cam
        assets = self.assets
        w, h = world.W, world.H
        for ty in range(miny, min(maxy, h)):
            row = world.tiles[ty]
            for tx in range(minx, min(maxx, w)):
                t = row[tx]
                x, y = cam.iso_to_screen(tx + 0.5, ty + 0.5,
                                         world.height_at(tx + 0.5, ty + 0.5) * config.TERRAIN_HEIGHT_SCALE)
                if x < -40 or x > self.W + 40 or y < -40 or y > self.H + 40:
                    continue
                if t == config.T_WATER:
                    continue
                if t == config.T_LILY:
                    spr = self._scale_sprite(assets.tile("water"),
                                             cam.zoom * 1.025)
                    self.screen.blit(spr, (x - spr.get_width() / 2,
                                           y - spr.get_height() / 2))
                    spr = self._scale_sprite(assets.spr["lily"])
                    self.screen.blit(spr, (x - spr.get_width() / 2,
                                           y - spr.get_height() / 2))
                    continue
                if t == config.T_BRIDGE:
                    spr = assets.tile("bridge")
                elif t == config.T_PATH:
                    spr = assets.tile("path")
                elif t == config.T_DIRT:
                    spr = assets.tile("dirt")
                elif t == config.T_ROCK:
                    spr = assets.tile("rock")
                else:
                    spr = assets.tile(
                        "grass", variant=world.grass_var[ty][tx])
                spr = self._scale_sprite(spr, self.cam.zoom * 1.025)
                self.screen.blit(spr, (x - spr.get_width() / 2,
                                       y - spr.get_height() / 2))

    # ------------------------------------------------------------------
    def _draw_water(self, world, minx, miny, maxx, maxy) -> None:
        cam = self.cam
        spr = self._scale_sprite(
            self.assets.tile("water"), cam.zoom * 1.025)
        half = (spr.get_width() / 2, spr.get_height() / 2)
        ripple = self.assets.spr.get("ripple")
        if ripple is not None and world.water_tiles:
            ripple = self._scale_sprite(ripple)
        phase = int(self.time * 1.7)
        t = self.time
        z = cam.zoom

        # Water tiles were previously traversed separately for the base,
        # shimmer and ripples, with repeated bounds checks and projections.
        # Process each visible water tile once and reuse its screen position.
        for i, (tx, ty) in enumerate(world.water_tiles):
            if tx < minx or tx > maxx or ty < miny or ty > maxy:
                continue
            if world.tiles[ty][tx] != config.T_WATER:
                continue
            x, y = cam.iso_to_screen(tx + 0.5, ty + 0.5, 0.0)
            if x < -40 or x > self.W + 40 or y < -40 or y > self.H + 40:
                continue

            self.screen.blit(spr, (x - half[0], y - half[1]))
            if (tx * 7 + ty * 13 + i) % 4 == 0:
                alpha = int(28 + 20 * math.sin(t * 2.2 + i))
                pygame.draw.ellipse(
                    self.screen, (150, 188, 205, alpha),
                    (int(x - 12 * z), int(y - 5 * z),
                     max(2, int(24 * z)), max(2, int(9 * z))), 0)

            if ripple is not None and (i + phase * 3) % 13 == 0:
                ripple.set_alpha(
                    42 + int(24 * (0.5 + 0.5 *
                                   math.sin(t * 2.0 + i))))
                self.screen.blit(ripple, (x - 20, y - 12))

    # ------------------------------------------------------------------
    def _depth_items(self, world, player, zombies, pickups,
                     visible_obstacles=None) -> list:
        if visible_obstacles is None:
            minx, miny, maxx, maxy = self._cull_bounds()
            visible_obstacles = world.cull_obstacles(
                minx, miny, maxx, maxy, pad=0.0)
        items = [(o.depth, "obs", o) for o in visible_obstacles]
        items.extend((z.depth, "zombie", z) for z in zombies if z.alive)
        items.extend((p.depth, "pickup", p) for p in pickups if not p.taken)
        if player is not None:
            items.append((player.depth, "player", player))
        # objective beacon above the shrine
        items.append((sum(world.shrine) + 0.4, "beacon", world.shrine))
        items.sort(key=lambda a: a[0])
        return items

    def _draw_item(self, item) -> None:
        # item is a 3-tuple: (depth, kind_string, object)
        # The kind_string selects which draw method handles it.
        _, key, obj = item
        if key == "obs":
            self._draw_obstacle(obj)
        elif key == "zombie":
            self._draw_zombie(obj)
        elif key == "pickup":
            self._draw_pickup(obj)
        elif key == "player":
            self._draw_player(obj)
        elif key == "beacon":
            self._draw_beacon(obj)

    def _shadow(self, x: float, y: float, size: float, alpha=90, z: float = 0.0) -> None:
        size = size * self.cam.zoom
        key = (int(size), int(alpha))
        s = self._shadow_cache.get(key)
        if s is None:
            s = pygame.Surface((max(2, int(size)),
                                max(2, int(size / 2))), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
            self._shadow_cache[key] = s
        cam = self.cam
        cx, cy = cam.iso_to_screen(x, y, z)
        self.screen.blit(s, (cx - s.get_width() / 2,
                             cy - s.get_height() / 2 + 4 * cam.zoom))

    def _white_flash(self, w: int, h: int, cx: int, cy: int,
                    alpha: int) -> None:
        key = (w, h)
        if key not in self._flashes:
            fs = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(fs, (255, 255, 255, 255),
                                (0, 0, w, h))
            self._flashes[key] = fs
        fs = self._flashes[key]
        fs.set_alpha(max(0, min(255, alpha)))
        self.screen.blit(fs, (cx - w // 2, cy - h // 2))

    def _draw_obstacle(self, o) -> None:
        if o.kind in ("fallen_log", "roots"):
            cam = self.cam
            cx, cy = cam.iso_to_screen(o.x, o.y, o.z)
            if not (-80 <= cx <= self.W + 80 and -80 <= cy <= self.H + 80):
                return
            scale = cam.zoom * o.scale
            if o.kind == "fallen_log":
                length = int(30 * scale)
                width = max(2, int(7 * scale))
                angle = ((o.variant * 37 + int(o.x * 13 + o.y * 7)) % 55) - 27
                radians = math.radians(angle)
                dx = math.cos(radians) * length * 0.5
                dy = math.sin(radians) * length * 0.5
                pygame.draw.line(self.screen, (54, 43, 31),
                                 (int(cx - dx), int(cy - dy)),
                                 (int(cx + dx), int(cy + dy)), width + 2)
                pygame.draw.line(self.screen, (103, 76, 48),
                                 (int(cx - dx * 0.82), int(cy - dy * 0.82)),
                                 (int(cx + dx * 0.82), int(cy + dy * 0.82)), width)
                pygame.draw.circle(self.screen, (126, 94, 60),
                                   (int(cx + dx), int(cy + dy)), max(2, width // 2))
            else:
                for arm in range(3):
                    angle = (o.variant * 41 + arm * 57) * math.pi / 180.0
                    ex = cx + math.cos(angle) * (8 + arm * 3) * scale
                    ey = cy + math.sin(angle) * (4 + arm) * scale
                    pygame.draw.line(self.screen, (76, 67, 48),
                                     (int(cx), int(cy)), (int(ex), int(ey)),
                                     max(1, int(2 * scale)))
            return
        spr = self._scale_sprite(self.assets.sprite(o.kind, o.variant),
                                 self.cam.zoom * o.scale)
        if o.kind == "tree" and self.quality >= 1:
            sway = int(round(math.sin(self.time * 1.15 +
                                      o.x * 0.63 + o.y * 0.41) * 1.25))
            if sway:
                key = (id(spr), sway)
                moved = self._tree_sway_cache.get(key)
                if moved is None:
                    moved = pygame.transform.rotate(spr, sway * 1.15)
                    self._tree_sway_cache[key] = moved
                spr = moved
        cam = self.cam
        cx, cy = cam.iso_to_screen(o.x, o.y, 0.0)
        if cx < -160 or cx > self.W + 160 or cy < -180 or cy > self.H + 80:
            return
        if o.kind in ("tree", "shrine", "waterfall", "ruin", "rock"):
            self._shadow(o.x, o.y, 30 if o.kind == "rock" else 42, 70, o.z)
        oy = -o.z * config.SCALE_Z * cam.zoom
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - spr.get_height() + oy + 8 * cam.zoom))
    def _draw_zombie(self, z) -> None:
        key = f"zombie_{z.ztype}"
        frames = self.assets.frames[key]
        flist = frames.get(z.anim_state, frames["idle"])
        cam = self.cam
        cx, cy = cam.iso_to_screen(z.x, z.y, z.z)
        self._shadow(z.x, z.y, 34, 80, z.z)
        def zombie_frame(state, index):
            choices = frames.get(state, frames["idle"])
            # Archetype proportions are already authored into the cached pose.
            # Scaling by type again here doubled size differences and distorted
            # stride/ground-contact relationships.
            frame = self._scale_sprite(choices[index % len(choices)])
            if z.facing < 0:
                cache_key = id(frame)
                flipped = self._flip_cache.get(cache_key)
                if flipped is None:
                    flipped = pygame.transform.flip(frame, True, False)
                    self._flip_cache[cache_key] = flipped
                frame = flipped
            return frame

        blend = max(0.0, min(1.0, float(getattr(z, "anim_blend", 1.0))))
        # Keep the ground anchor fixed while moving. Bob and lateral sway
        # are authored inside cached pose frames; translating the whole sprite
        # here made planted feet visibly skate across the terrain.
        base_y = cy
        if blend < 1.0 and z.prev_anim_state != z.anim_state:
            previous = zombie_frame(z.prev_anim_state,
                                    z.prev_frame_index).copy()
            previous.set_alpha(int(255 * (1.0 - blend)))
            self.screen.blit(previous, (cx - previous.get_width() / 2,
                                         base_y - previous.get_height()
                                         + 10 * cam.zoom))
        spr = zombie_frame(z.anim_state, z.frame_index)
        if blend < 1.0:
            spr = spr.copy()
            spr.set_alpha(int(255 * blend))
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               base_y - spr.get_height() + 10 * cam.zoom))
        if z.hit_flash > 0:
            self._white_flash(30, 40, int(cx), int(cy - 22),
                              int(180 * z.hit_flash / 0.12))
        # HP bar for damaged zombies
        if z.hp < z.max_hp:
            bw = int(26 * cam.zoom)
            ratio = max(0.0, z.hp / z.max_hp)
            bx = cx - bw / 2
            by = cy - (spr.get_height()) - 6
            pygame.draw.rect(self.screen, (40, 40, 40), (bx, by, bw, max(2, int(3 * cam.zoom))))
            pygame.draw.rect(self.screen, (200, 50, 40),
                             (bx, by, int(bw * ratio), max(2, int(3 * cam.zoom))))

    def _draw_pickup(self, p) -> None:
        spr = self._scale_sprite(self.assets.spr[p.ptype])
        cam = self.cam
        cx, cy = cam.iso_to_screen(p.x, p.y, getattr(p, "z", 0.0))
        bob = math.sin(p.bob * 3.0) * 3 * cam.zoom
        self._shadow(p.x, p.y, 20, 60, getattr(p, "z", 0.0))
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - spr.get_height() - 6 * cam.zoom + bob))
        # soft glow ring
        pygame.draw.ellipse(self.screen, (255, 230, 150, 60),
                            (cx - 14 * cam.zoom, cy - 2 * cam.zoom,
                             28 * cam.zoom, 12 * cam.zoom))

    def _draw_beacon(self, pos) -> None:
        cam = self.cam
        cx, cy = cam.iso_to_screen(pos[0] + 0.5, pos[1] + 0.5, 0.0)
        spr = self._scale_sprite(self.assets.spr["beacon"])
        off = math.sin(self.time * 2.0) * 4 * cam.zoom
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - 120 * cam.zoom + off))
        a = int(150 + 70 * math.sin(self.time * 3))
        self._beacon_glow.set_alpha(a)
        glow = self._scale_sprite(self._beacon_glow)
        self.screen.blit(glow, (cx - glow.get_width() / 2,
                                cy - 136 * cam.zoom + off))

    # ------------------------------------------------------------------
    def _draw_player(self, p) -> None:
        cam = self.cam
        cx, cy = cam.iso_to_screen(p.x, p.y, 0.0)
        self._shadow(p.x, p.y, 34, 90, p.z)

        # Read the live weapon/action flags as well as anim_state. Input is
        # processed after Player.update(), so anim_state can still be "run"
        # for the frame in which fire/reload begins.
        weapon_action = (
            not p.crouching and
            (bool(getattr(p.weapon, "reloading", False)) or
             float(getattr(p, "_shoot_flash", 0.0)) > 0.0)
        )

        def frame_for(state, frame_index):
            # Weapon actions always use the neutral idle pose. This is based
            # on the live action flags, not only the possibly stale anim_state.
            if weapon_action or state in ("shoot", "reload"):
                state = "idle"
                frame_index = 0
            frames = self.assets.player_frames(state)
            frame = self._scale_sprite(frames[frame_index % len(frames)])
            if p.facing < 0:
                key = id(frame)
                flipped = self._flip_cache.get(key)
                if flipped is None:
                    flipped = pygame.transform.flip(frame, True, False)
                    self._flip_cache[key] = flipped
                frame = flipped
            return frame

        blend = max(0.0, min(1.0, float(getattr(p, "anim_blend", 1.0))))
        # Ease the blend curve so the outgoing pose fades faster at the edges
        # and the new pose settles in smoothly -- a smoother morph than a flat
        # linear alpha crossfade, with no visible double-exposure ghost.
        eased = blend * blend * (3.0 - 2.0 * blend)
        if weapon_action:
            # Do not let the outgoing locomotion pose show through or fade
            # the neutral action pose during the input/update ordering gap.
            eased = 1.0
        anchor_y = cy - 0 + 10 * cam.zoom
        if (not weapon_action and eased < 1.0
                and p.prev_anim_state != p.anim_state
                and p.anim_state not in ("shoot", "reload")):
            previous = frame_for(p.prev_anim_state, p.prev_frame_index).copy()
            previous.set_alpha(int(255 * (1.0 - eased)))
            # Align both frames on the same ground anchor so the planted feet
            # do not shift sideways while the pose morphs.
            px = cx - (previous.get_width() // 2)
            py = anchor_y - previous.get_height()
            self.screen.blit(previous, (px, py))
        # Dedicated weapon sheets override locomotion only while the
        # corresponding action is active. Their frame counts also distinguish
        # a loaded sheet from the short neutral fallback used when absent.
        action_frames = None
        action_index = 0
        if not p.crouching and bool(getattr(p.weapon, "reloading", False)):
            reload_frames = self.assets.player_frames("reload_action")
            if len(reload_frames) >= 9:
                action_frames = reload_frames
                progress = max(0.0, min(
                    1.0, float(getattr(p.weapon, "reload_progress", 0.0))))
                action_index = min(8, int(progress * 9.0))
        elif not p.crouching and float(getattr(p, "_shoot_flash", 0.0)) > 0.0:
            fire_frames = self.assets.player_frames("fire_action")
            if len(fire_frames) >= 8:
                action_frames = fire_frames
                elapsed = max(0.0, 0.24 - float(p._shoot_flash))
                action_index = min(7, int(elapsed / 0.03))

        if action_frames is not None:
            spr = self._scale_sprite(action_frames[action_index])
            if p.facing < 0:
                key = id(spr)
                flipped = self._flip_cache.get(key)
                if flipped is None:
                    flipped = pygame.transform.flip(spr, True, False)
                    self._flip_cache[key] = flipped
                spr = flipped
            eased = 1.0
        else:
            spr = frame_for(p.anim_state, p.frame_index)

        # Crouch poses are already authored in the correct lowered/leaning
        # posture. Do not rotate them again; that distorts the provided art.
        if eased < 1.0:
            spr = spr.copy()
            spr.set_alpha(int(255 * eased))
        # flicker while invulnerable
        if p.invuln > 0 and int(p.invuln * 20) % 2 == 0:
            spr = spr.copy()
            spr.set_alpha(120 if eased >= 1.0 else
                          int(120 * eased))
        # Torso bob and lean are authored inside the cached pose. Never
        # offset the complete sprite during a stride: the feet stay pinned
        # to the isometric ground anchor instead of sliding or floating.
        self.screen.blit(spr, (cx - spr.get_width() // 2,
                               anchor_y - spr.get_height()))
        if p.dmg_flash > 0:
            self._white_flash(30, 40, int(cx), int(cy - 22),
                              int(200 * p.dmg_flash))
        # muzzle flash
        if p._shoot_flash > 0:
            mx, my = cam.iso_to_screen(p.x + p.aim[0] * 0.7,
                                       p.y + p.aim[1] * 0.7, p.z + 0.3)
            m = self._scale_sprite(self.assets.spr["muzzle"])
            self.screen.blit(m, (mx - m.get_width() / 2,
                                 my - m.get_height() / 2 - 4 * cam.zoom))

    def _draw_bullets(self, bullets) -> None:
        cam = self.cam
        tracer = self._scale_sprite(self.assets.spr["tracer"])
        for b in bullets:
            x, y = cam.iso_to_screen(b.x, b.y, b.z)
            ex, ey = cam.iso_to_screen(b.x - b.dx * 0.5,
                                       b.y - b.dy * 0.5, b.z)
            dx = x - ex
            dy = y - ey
            ang = math.atan2(dy, dx)
            rot = pygame.transform.rotate(tracer, -math.degrees(ang))
            self.screen.blit(rot, (x - rot.get_width() / 2,
                                   y - rot.get_height() / 2))
            if b.pellets > 1:
                p = self._scale_sprite(self.assets.spr["pellet"])
                self.screen.blit(p, (x - 3 * cam.zoom, y - 3 * cam.zoom))

    def _draw_grenades(self, grenades) -> None:
        for grenade in grenades:
            x, y = self.cam.iso_to_screen(grenade["x"], grenade["y"], 0.18)
            radius = max(3, int(5 * self.cam.zoom))
            pygame.draw.circle(self.screen, (45, 52, 42), (int(x), int(y)), radius + 2)
            pygame.draw.circle(self.screen, (125, 145, 95), (int(x), int(y)), radius)
            pygame.draw.circle(self.screen, (220, 190, 115),
                               (int(x - radius * 0.35), int(y - radius * 0.35)),
                               max(1, radius // 3))

    def _draw_particles(self) -> None:
        self.particles.draw(self.screen, self.cam, self.quality)

    # ------------------------------------------------------------------
    def tick_weather(self, dt: float, world=None) -> Optional[str]:
        """Advance the weather clock, shake decay and ambient particles.

        Returns a weather event name ("lightning") when it fired this
        frame so the caller can hook sounds; the visual reactions
        (flash, shake) are applied here automatically.
        """
        self.shake.update(dt)
        ev = self.weather.update(dt)
        self.particles.set_wind(self.weather.wind * self.weather.wind_dir)
        if ev == "lightning":
            self.post.on_lightning(self.weather.lightning)
            # Pick a real location in the forest map. The bolt is world-anchored
            # and may remain off-screen while its atmospheric flash is visible.
            if world is not None:
                self._lightning_strike = (
                    random.uniform(2.0, max(2.1, world.W - 2.0)),
                    random.uniform(2.0, max(2.1, world.H - 2.0)))
            self.shake.add(7.0, 0.72)
        return ev

    # ------------------------------------------------------------------
    def set_battery(self, battery: float) -> None:
        """Feed the survival system's flashlight battery to the lighting
        layer (drives the critical-low flicker)."""
        self._battery = float(battery)

    # ------------------------------------------------------------------
    def _draw_rain(self, dt: float, world=None) -> None:
        """Render rain as world-anchored 3D drops that fall onto real terrain."""
        w = self.weather
        layer = self._rain_layer
        layer.fill((0, 0, 0, 0))
        if world is None or w.rain_amount < 0.06 or self.quality < 1:
            self._rain.clear()
            self._splashes.clear()
            return

        scale = quality_settings.particle_scale(self.quality)
        target = int((260 + 420 * w.rain_amount) * scale)
        minx, miny, maxx, maxy = self._cull_bounds()
        minx, miny = max(0, minx - 3), max(0, miny - 3)
        maxx, maxy = min(world.W, maxx + 3), min(world.H, maxy + 3)

        # Each drop lives at a world x/y coordinate and a real height above
        # the ground. Camera movement therefore reveals new rain in the world
        # instead of carrying a fixed screen-space rain texture with the player.
        while len(self._rain) < target:
            self._rain.append([
                random.uniform(minx, max(minx + 0.01, maxx)),
                random.uniform(miny, max(miny + 0.01, maxy)),
                random.uniform(2.5, 7.5),
                random.uniform(0.65, 1.45),
                random.uniform(0.45, 1.0)])
        if len(self._rain) > target:
            del self._rain[target:]

        wind = w.wind * w.wind_dir
        alive_drops = []
        for drop in self._rain:
            wx, wy, z, speed, depth = drop
            speed *= (0.9 + 0.45 * w.rain_amount)
            wx += wind * (0.8 + depth * 1.8) * dt
            wy += wind * 0.22 * dt
            old_z = z
            z -= speed * (2.8 + depth * 1.8) * dt

            if z <= 0.0:
                tx, ty = int(wx), int(wy)
                if 0 <= tx < world.W and 0 <= ty < world.H:
                    if world.tiles[ty][tx] != config.T_WATER:
                        self._splashes.append([
                            wx, wy, random.uniform(0.12, 0.28), 0.28,
                            random.uniform(0.12, 0.22)])
                continue

            sx, sy = self.cam.iso_to_screen(wx, wy, z)
            ex, ey = self.cam.iso_to_screen(wx - wind * 0.10,
                                             wy - wind * 0.025,
                                             max(0.0, old_z - 0.8))
            if -30 <= sx <= self.W + 30 and -40 <= sy <= self.H + 40:
                alpha = int((75 + 145 * depth) * w.rain_amount)
                color = (145 + int(30 * depth), 174 + int(28 * depth),
                         205 + int(25 * depth), min(235, alpha))
                pygame.draw.line(layer, color, (int(sx), int(sy)),
                                 (int(ex), int(ey)),
                                 1 if depth < 0.78 else 2)
            # Recycle drops that leave the simulated world bounds.
            if minx - 4 <= wx <= maxx + 4 and miny - 4 <= wy <= maxy + 4:
                alive_drops.append([wx, wy, z, drop[3], depth])
        self._rain = alive_drops

        # Splash rings are stored on the terrain too, so they remain in place
        # as the camera pans and are projected through the same isometric view.
        alive_splashes = []
        for wx, wy, life, duration, radius in self._splashes:
            life -= dt
            if life <= 0:
                continue
            progress = 1.0 - life / duration
            sx, sy = self.cam.iso_to_screen(wx, wy, 0.0)
            rx = max(1, int(radius * self.cam.zoom *
                            (0.45 + progress * 2.0) * 32))
            ry = max(1, int(rx * 0.30))
            alpha = int(170 * (1.0 - progress))
            if -24 <= sx <= self.W + 24 and -24 <= sy <= self.H + 24:
                pygame.draw.ellipse(layer, (175, 205, 225, alpha),
                                    (int(sx - rx), int(sy - ry),
                                     rx * 2, ry * 2), 1)
                if progress < 0.24:
                    crown = max(1, int(rx * (1.0 - progress)))
                    pygame.draw.arc(layer, (215, 230, 242, alpha),
                                    (int(sx - crown), int(sy - crown * 0.5),
                                     crown * 2, max(2, crown)),
                                    0.12, 3.02, 1)
            alive_splashes.append([wx, wy, life, duration, radius])
        self._splashes = alive_splashes
        self.screen.blit(layer, (0, 0))

    def _draw_lightning_bolt(self) -> None:
        """Draw a branching lightning strike anchored to a world location."""
        if self._lightning_strike is None or self.weather.lightning <= 0.03:
            return
        wx, wy = self._lightning_strike
        top = self.cam.iso_to_screen(wx, wy, 8.5)
        ground = self.cam.iso_to_screen(wx, wy, 0.0)
        if not (-180 <= ground[0] <= self.W + 180 and
                -220 <= ground[1] <= self.H + 180):
            return

        # Deterministic branches: the strike jitters in height, but does not
        # jump around the screen as the camera moves.
        rng = random.Random(int(wx * 7919 + wy * 104729))
        points = [top]
        for i in range(1, 9):
            z = 8.5 * (1.0 - i / 9.0)
            px = wx + rng.uniform(-0.42, 0.42)
            py = wy + rng.uniform(-0.28, 0.28)
            points.append(self.cam.iso_to_screen(px, py, z))
        points.append(ground)
        pts = [(int(x), int(y)) for x, y in points]
        pygame.draw.lines(self.screen, (95, 145, 205), False, pts, 5)
        pygame.draw.lines(self.screen, (205, 226, 255), False, pts, 2)
        pygame.draw.lines(self.screen, (245, 250, 255), False, pts, 1)

        # A few short forks branch from the main channel toward the ground.
        for index in (2, 4, 6):
            x, y = pts[index]
            fork = [(x, y), (x + rng.randint(-22, 22),
                              y + rng.randint(12, 30)),
                    (x + rng.randint(-34, 34),
                     y + rng.randint(28, 48))]
            pygame.draw.lines(self.screen, (185, 215, 250), False, fork, 1)

        # Ground flash is localized at the strike point, not attached to player.
        gx, gy = ground
        self._lightning_glow.set_alpha(
            int(115 * self.weather.lightning))
        self.screen.blit(self._lightning_glow,
                         (int(gx - 56), int(gy - 32)))

    def _draw_weather_tint(self) -> None:
        """Subtle cool wet-weather grading and a brief whole-scene lightning flash."""
        amount = self.weather.rain_amount
        self._weather_tint.fill((12, 22, 38, int(22 * amount)))
        self.screen.blit(self._weather_tint, (0, 0))

    # ------------------------------------------------------------------
    def _enemy_lights(self, player, zombies: Sequence):
        """Subtle cool glow around nearby pursuing enemies (max 4, so
        light sources never reveal positions across the map)."""
        out = []
        if player is None:
            return out
        for z in zombies:
            if len(out) >= 4:
                break
            if not z.alive or z.state not in ("pursue", "attack",
                                              "investigating", "searching"):
                continue
            if z.dist2(player) > 30.0:
                continue
            sx, sy = self.cam.iso_to_screen(z.x, z.y, 0.0)
            out.append((sx, sy, 2.6, 0.30))
        return out

    # ------------------------------------------------------------------
    def _apply_lighting(self, world, player, zombies=()) -> None:
        # Lighting and post-processing are cached by VisualEnhancement.
        # Keep a stable integration point for all quality presets and avoid
        # rebuilding full-resolution NumPy arrays on every frame.
        fog_beam = self.weather.rain_amount > 0.2
        # Zombies receive no artificial glow: they stay hidden until the
        # flashlight or a real environmental light source illuminates them.
        self.visual.apply_lighting(
            self.screen, self.cam, world, player, self.quality,
            battery=self._battery, fog_beam=fog_beam,
            time_value=self.time)

    # ------------------------------------------------------------------
    def render_frame(self, world, player, zombies, pickups, bullets,
                     dt: float, tension: float = 0.0,
                     grenades: Sequence = ()) -> None:
        """Render one full frame: world -> rain -> lighting ->
        cinematic post-processing.  The HUD is drawn by the caller on top
        of the result, so UI stays perfectly readable."""
        self.time += dt
        if dt > 0:
            self._fps = self._fps * 0.9 + (1.0 / dt) * 0.1
        self.screen.fill((30, 26, 20))
        self.draw_world(world, player, zombies, pickups, bullets, grenades)
        self._draw_rain(dt, world)
        self._draw_weather_tint()
        # -- cinematic post-processing (before the HUD) ------------------
        if player is not None:
            hp = getattr(player, "hp", 0.0)
            if self._last_hp is not None and hp < self._last_hp - 0.01:
                amt = min(1.0, (self._last_hp - hp) / 12.0)
                self.post.on_damage(amt)
                self.shake.add(4.0, 0.5)
            self._last_hp = hp
            w = player.weapon
            if w is not None and w.muzzle_timer > 0.04:
                self.shake.add(1.4, 0.18)     # restrained recoil kick
        self.post.update(dt, tension)
        if self.post.enabled:
            self.post.scene.blit(self.screen, (0, 0))
            off = self.shake.offset()
            if off != (0, 0):
                self.screen.fill((16, 13, 10))  # hide the exposed edge strip
            self.post.present(self.screen, player,
                              low_hp=(player is not None and
                                      player.hp < 30.0),
                              dt=dt, tension=tension, offset=off)
        # Flashlight state no longer applies a full-screen darkness overlay.
        # Ambient world lighting stays consistent; only the directional beam
        # is toggled in VisualEnhancement.apply_lighting().

        # Lightning briefly illuminates the full scene after post-processing,
        # but before the HUD, so UI text remains crisp and readable.
        flash = float(self.weather.lightning)
        if flash > 0.02:
            # Brief blue-white atmospheric flash after the world-space bolt.
            flash_alpha = max(0, min(225, int(18 + 205 * flash)))
            self._lightning_flash.fill((205, 222, 245, flash_alpha))
            self.screen.blit(self._lightning_flash, (0, 0))
            self._draw_lightning_bolt()
        elif flash <= 0.0:
            self._lightning_strike = None

        if self.show_debug:
            self._draw_debug()



    # ------------------------------------------------------------------
    def _draw_debug(self) -> None:
        d = self._dbg_counts
        if not d:
            return
        if self._dbg_font is None:
            self._dbg_font = pygame.font.SysFont(
                "consolas,couriernew,monospace", 16)
        lines = [
            f"FPS: {self._fps:5.1f}",
            f"Player world: ({d['player_x']:.2f}, {d['player_y']:.2f})",
            f"Player screen: ({d['player_sx']:.0f}, {d['player_sy']:.0f})",
            f"Camera: ({d['cam_x']:.2f}, {d['cam_y']:.2f})  zoom={d['cam_zoom']:.2f}",
            f"Map tiles: {d['tiles_total']}",
            f"Obstacles total/visible: {d['obstacles_total']}/{d['obstacles_visible']}",
            f"Depth items: {d['depth_items']}  drawn: {d['drawn_items']}",
            f"Zombies: {d['zombies']}  Pickups: {d['pickups']}  Bullets: {d['bullets']}",
        ]
        x, y = 12, self.H - len(lines) * 20 - 12
        bg = pygame.Surface((360, len(lines) * 20 + 8), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        self.screen.blit(bg, (x - 6, y - 4))
        for line in lines:
            surf = self._dbg_font.render(line, True, (200, 255, 160))
            self.screen.blit(surf, (x, y))
            y += 20

