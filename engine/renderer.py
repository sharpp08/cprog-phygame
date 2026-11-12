"""Isometric world renderer: ground, water, obstacles, characters, effects,
lighting and fog.  Everything is drawn in screen space through the camera;
world coordinates never leak into the UI layer.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import pygame

from engine.visual_enhancement import VisualEnhancement

import config
from engine.collision import distance2


class Renderer:
    def __init__(self, screen, cam, assets, particles) -> None:
        self.screen = screen
        self.cam = cam
        self.assets = assets
        self.particles = particles
        self.W = config.WINDOW_W
        self.H = config.WINDOW_H
        self.quality = 1
        self.time = 0.0
        self.visual = VisualEnhancement(self.W, self.H)
        self._shadow_cache: dict = {}
        self._scaled_cache: dict = {}
        self._tree_sway_cache: dict = {}
        self._flip_cache: dict = {}
        self._beacon_glow = pygame.Surface((48, 48), pygame.SRCALPHA)
        pygame.draw.circle(self._beacon_glow, (255, 210, 120, 110),
                           (24, 24), 23)
        pygame.draw.circle(self._beacon_glow, (255, 235, 170, 70),
                           (24, 24), 14)
        self._fog: Optional[pygame.Surface] = None
        self._dim: Optional[pygame.Surface] = None
        self._flashes: dict = {}
        self.show_debug = False
        self._fps = 0.0
        self._dbg_font = None
        self._dbg_counts: dict = {}
        self._prep_fog()

    # ------------------------------------------------------------------
    def _prep_fog(self) -> None:
        self.visual.resize(self.W, self.H)
        fog = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for y in range(self.H):
            a = int(90 * (y / self.H) ** 2)
            pygame.draw.line(fog, (190, 170, 140, a), (0, y), (self.W, y))
        self._fog = fog
        dim = pygame.Surface((self.W, self.H))
        dim.fill((208, 202, 186))
        self._dim = dim

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
                   bullets: Sequence) -> None:
        cam = self.cam
        minx, miny, maxx, maxy = self._cull_bounds()
        self._draw_ground(world, minx, miny, maxx, maxy)
        self._draw_water(world, minx, miny, maxx, maxy)
        items = self._depth_items(world, player, zombies, pickups)
        drawn_items = 0
        for it in items:
            self._draw_item(it)
            drawn_items += 1
        self._draw_bullets(bullets)
        self._draw_particles()
        self._apply_lighting(world, player)
        self.visual.draw_atmosphere(self.screen, self.cam, world,
                                    self.time, self.quality)
        # cache counts for the debug overlay
        cam_x, cam_y = cam.fx, cam.fy
        psx, psy = cam.iso_to_screen(player.x, player.y, 0.0) \
            if player is not None else (0.0, 0.0)
        self._dbg_counts = {
            "tiles_total": world.W * world.H,
            "obstacles_total": len(world.obstacles),
            "obstacles_visible": sum(1 for o in world.obstacles
                                     if o.in_rect(minx, miny, maxx, maxy, 0.0)),
            "depth_items": len(items),
            "drawn_items": drawn_items,
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
                x, y = cam.iso_to_screen(tx + 0.5, ty + 0.5, 0.0)
                if x < -40 or x > self.W + 40 or y < -40 or y > self.H + 40:
                    continue
                if t == config.T_WATER:
                    continue
                if t == config.T_LILY:
                    spr = assets.tile("water")
                    self.screen.blit(spr, (x - spr.get_width() / 2,
                                           y - spr.get_height() / 2))
                    spr = assets.spr("lily")
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
        spr = self._scale_sprite(self.assets.tile("water"), self.cam.zoom * 1.025)
        half = (spr.get_width() / 2, spr.get_height() / 2)
        for (tx, ty) in world.water_tiles:
            if tx > maxx or tx < minx or ty > maxy or ty < miny:
                continue
            if world.tiles[ty][tx] != config.T_WATER:
                continue
            x, y = cam.iso_to_screen(tx + 0.5, ty + 0.5, 0.0)
            if x < -40 or x > self.W + 40 or y < -40 or y > self.H + 40:
                continue
            self.screen.blit(spr, (x - half[0], y - half[1]))
        # animated shimmer highlights
        t = self.time
        for i, (tx, ty) in enumerate(world.water_tiles):
            if tx > maxx or tx < minx or ty > maxy or ty < miny:
                continue
            if (tx * 7 + ty * 13 + i) % 4:
                continue
            x, y = cam.iso_to_screen(tx + 0.5, ty + 0.5, 0.0)
            a = int(28 + 20 * math.sin(t * 2.2 + i))
            z = self.cam.zoom
            pygame.draw.ellipse(self.screen,
                                (150, 188, 205, a),
                                (int(x - 12 * z), int(y - 5 * z),
                                 max(2, int(24 * z)),
                                 max(2, int(9 * z))), 0)
        # A few larger, translucent ripple rings sell the water movement.
        ripple = self.assets.spr.get("ripple")
        if ripple is not None and world.water_tiles:
            ripple = self._scale_sprite(ripple)
            phase = int(self.time * 1.7)
            for i, (tx, ty) in enumerate(world.water_tiles):
                if (i + phase * 3) % 13:
                    continue
                if tx < minx or tx > maxx or ty < miny or ty > maxy:
                    continue
                x, y = cam.iso_to_screen(tx + 0.5, ty + 0.5, 0.0)
                ripple.set_alpha(42 + int(24 * (0.5 + 0.5 *
                                                math.sin(self.time * 2 + i))))
                self.screen.blit(ripple, (x - 20, y - 12))

    # ------------------------------------------------------------------
    def _depth_items(self, world, player, zombies, pickups) -> list:
        minx, miny, maxx, maxy = self._cull_bounds()
        items = []
        for o in world.cull_obstacles(minx, miny, maxx, maxy, pad=0.0):
            items.append((o.depth, "obs", o))
        for z in zombies:
            if not z.alive:
                continue
            items.append((z.depth, "zombie", z))
        for p in pickups:
            if not p.taken:
                items.append((p.depth, "pickup", p))
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

    def _shadow(self, x: float, y: float, size: float, alpha=90) -> None:
        size = size * self.cam.zoom
        key = (int(size), int(alpha))
        s = self._shadow_cache.get(key)
        if s is None:
            s = pygame.Surface((max(2, int(size)),
                                max(2, int(size / 2))), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
            self._shadow_cache[key] = s
        cam = self.cam
        cx, cy = cam.iso_to_screen(x, y, 0.0)
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
        spr = self._scale_sprite(self.assets.sprite(o.kind, o.variant))
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
            self._shadow(o.x, o.y, 30 if o.kind == "rock" else 42, 70)
        oy = -o.z * config.SCALE_Z * cam.zoom
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - spr.get_height() + oy + 8 * cam.zoom))
        if o.kind == "waterfall" and self.quality >= 1:
            mist = self.assets.spr.get("mist")
            if mist is not None:
                mist = self._scale_sprite(mist)
                mist.set_alpha(105 if self.quality == 1 else 145)
                drift = math.sin(self.time * 0.8) * 5
                self.screen.blit(mist, (cx - 42 + drift,
                                         cy - 32 + math.sin(
                                             self.time * 1.3) * 2))

    def _draw_zombie(self, z) -> None:
        key = f"zombie_{z.ztype}"
        frames = self.assets.frames[key]
        flist = frames.get(z.anim_state, frames["idle"])
        spr = flist[z.frame_index % len(flist)]
        cam = self.cam
        cx, cy = cam.iso_to_screen(z.x, z.y, 0.0)
        self._shadow(z.x, z.y, 34, 80)
        type_scale = 1.3 if z.ztype == "tank" else (
            0.92 if z.ztype == "fast" else 1.0)
        spr = self._scale_sprite(spr, self.cam.zoom * type_scale)
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - spr.get_height() + 10 * cam.zoom))
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
        cx, cy = cam.iso_to_screen(p.x, p.y, 0.0)
        bob = math.sin(p.bob * 3.0) * 3 * cam.zoom
        self._shadow(p.x, p.y, 20, 60)
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
        self._shadow(p.x, p.y, 34, 90)
        flist = self.assets.player_frames(p.anim_state)
        spr = self._scale_sprite(flist[p.frame_index % len(flist)])
        if p.facing < 0:
            key = id(spr)
            flipped = self._flip_cache.get(key)
            if flipped is None:
                flipped = pygame.transform.flip(spr, True, False)
                self._flip_cache[key] = flipped
            spr = flipped
        # flicker while invulnerable
        if p.invuln > 0 and int(p.invuln * 20) % 2 == 0:
            spr = spr.copy()
            spr.set_alpha(120)
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - spr.get_height() + 10))
        if p.dmg_flash > 0:
            self._white_flash(30, 40, int(cx), int(cy - 22),
                              int(200 * p.dmg_flash))
        # muzzle flash
        if p._shoot_flash > 0:
            mx, my = cam.iso_to_screen(p.x + p.aim[0] * 0.7,
                                       p.y + p.aim[1] * 0.7, 0.3)
            m = self._scale_sprite(self.assets.spr["muzzle"])
            self.screen.blit(m, (mx - m.get_width() / 2,
                                 my - m.get_height() / 2 - 4))

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

    def _draw_particles(self) -> None:
        self.particles.draw(self.screen, self.cam, self.quality)

    # ------------------------------------------------------------------
    def _apply_lighting(self, world, player) -> None:
        # Lighting and post-processing are cached by VisualEnhancement.
        # Keep a stable integration point for all quality presets and avoid
        # rebuilding full-resolution NumPy arrays on every frame.
        self.visual.apply_lighting(self.screen, self.cam, world, player,
                                   self.quality)

    # ------------------------------------------------------------------
    def render_frame(self, world, player, zombies, pickups, bullets,
                     dt: float) -> None:
        self.time += dt
        if dt > 0:
            self._fps = self._fps * 0.9 + (1.0 / dt) * 0.1
        self.screen.fill((30, 26, 20))
        self.draw_world(world, player, zombies, pickups, bullets)
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

