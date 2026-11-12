"""Isometric world renderer: ground, water, obstacles, characters, effects,
lighting and fog.  Everything is drawn in screen space through the camera;
world coordinates never leak into the UI layer.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pygame

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
        self._lightmap: Optional[pygame.Surface] = None
        self._mesh: Optional[Tuple[np.ndarray, np.ndarray]] = None
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
        fog = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for y in range(self.H):
            a = int(90 * (y / self.H) ** 2)
            pygame.draw.line(fog, (190, 170, 140, a), (0, y), (self.W, y))
        self._fog = fog
        dim = pygame.Surface((self.W, self.H))
        dim.fill((208, 202, 186))
        self._dim = dim

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
        if self.quality >= 1:
            self._apply_lighting(world, player)
        else:
            self.screen.blit(self._dim, (0, 0),
                             special_flags=pygame.BLEND_RGB_MULT)
        if self.quality >= 2 and self._fog:
            self.screen.blit(self._fog, (0, 0))
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
                self.screen.blit(spr, (x - spr.get_width() / 2,
                                       y - spr.get_height() / 2))

    # ------------------------------------------------------------------
    def _draw_water(self, world, minx, miny, maxx, maxy) -> None:
        cam = self.cam
        spr = self.assets.tile("water")
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
            pygame.draw.ellipse(self.screen,
                                (190, 220, 240, a),
                                (int(x - 12), int(y - 5), 24, 9), 0)

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
        s = pygame.Surface((int(size), int(size / 2)), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
        cam = self.cam
        cx, cy = cam.iso_to_screen(x, y, 0.0)
        self.screen.blit(s, (cx - s.get_width() / 2,
                             cy - s.get_height() / 2 + 4))

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
        spr = self.assets.sprite(o.kind, o.variant)
        cam = self.cam
        cx, cy = cam.iso_to_screen(o.x, o.y, 0.0)
        if cx < -160 or cx > self.W + 160 or cy < -180 or cy > self.H + 80:
            return
        if o.kind in ("tree", "shrine", "waterfall", "ruin", "rock"):
            self._shadow(o.x, o.y, 30 if o.kind == "rock" else 42, 70)
        oy = -o.z * config.SCALE_Z
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - spr.get_height() + oy + 8))

    def _draw_zombie(self, z) -> None:
        key = f"zombie_{z.ztype}"
        frames = self.assets.frames[key]
        flist = frames.get(z.anim_state, frames["idle"])
        spr = flist[z.frame_index % len(flist)]
        cam = self.cam
        cx, cy = cam.iso_to_screen(z.x, z.y, 0.0)
        self._shadow(z.x, z.y, 34, 80)
        scale = 1.3 if z.ztype == "tank" else 1.0
        if scale != 1.0:
            spr = pygame.transform.scale(spr,
                                        (int(spr.get_width() * scale),
                                         int(spr.get_height() * scale)))
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - spr.get_height() + 10))
        if z.hit_flash > 0:
            self._white_flash(30, 40, int(cx), int(cy - 22),
                              int(180 * z.hit_flash / 0.12))
        # HP bar for damaged zombies
        if z.hp < z.max_hp:
            bw = 26
            ratio = max(0.0, z.hp / z.max_hp)
            bx = cx - bw / 2
            by = cy - (spr.get_height()) - 6
            pygame.draw.rect(self.screen, (40, 40, 40), (bx, by, bw, 3))
            pygame.draw.rect(self.screen, (200, 50, 40),
                             (bx, by, int(bw * ratio), 3))

    def _draw_pickup(self, p) -> None:
        spr = self.assets.spr[p.ptype]
        cam = self.cam
        cx, cy = cam.iso_to_screen(p.x, p.y, 0.0)
        bob = math.sin(p.bob * 3.0) * 3
        self._shadow(p.x, p.y, 20, 60)
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - spr.get_height() - 6 + bob))
        # soft glow ring
        pygame.draw.ellipse(self.screen, (255, 230, 150, 60),
                            (cx - 14, cy - 2, 28, 12))

    def _draw_beacon(self, pos) -> None:
        cam = self.cam
        cx, cy = cam.iso_to_screen(pos[0] + 0.5, pos[1] + 0.5, 0.0)
        spr = self.assets.spr["beacon"]
        off = math.sin(self.time * 2.0) * 4
        self.screen.blit(spr, (cx - spr.get_width() / 2,
                               cy - 120 + off))
        glow = pygame.Surface((40, 40), pygame.SRCALPHA)
        a = int(90 + 50 * math.sin(self.time * 3))
        pygame.draw.circle(glow, (255, 220, 120, a), (20, 20), 20)
        self.screen.blit(glow, (cx - 20, cy - 130 + off - 6))

    # ------------------------------------------------------------------
    def _draw_player(self, p) -> None:
        cam = self.cam
        cx, cy = cam.iso_to_screen(p.x, p.y, 0.0)
        self._shadow(p.x, p.y, 34, 90)
        flist = self.assets.player_frames(p.anim_state)
        spr = flist[p.frame_index % len(flist)]
        if p.facing < 0:
            spr = pygame.transform.flip(spr, True, False)
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
            m = self.assets.spr["muzzle"]
            self.screen.blit(m, (mx - m.get_width() / 2,
                                 my - m.get_height() / 2 - 4))

    def _draw_bullets(self, bullets) -> None:
        cam = self.cam
        tracer = self.assets.spr["tracer"]
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
                p = self.assets.spr["pellet"]
                self.screen.blit(p, (x - 3, y - 3))

    def _draw_particles(self) -> None:
        self.particles.draw(self.screen, self.cam, self.quality)

    # ------------------------------------------------------------------
    def _apply_lighting(self, world, player) -> None:
        H, W = self.H, self.W
        if self._mesh is None:
            yy, xx = np.meshgrid(np.arange(H), np.arange(W),
                                 indexing="ij")
            self._mesh = (xx.astype(np.float32), yy.astype(np.float32))
        xx, yy = self._mesh
        ambient = 0.82
        lum = np.full((H, W), ambient, dtype=np.float32)
        z = self.cam.zoom
        lights = []
        for (wx, wy, r, inten) in world.lights:
            lights.append((wx, wy, r * z * 4.0, inten))
        lights.append((player.x, player.y, 11.0 * z, 0.55))
        for (wx, wy, rpx, inten) in lights:
            lx, ly = self.cam.iso_to_screen(wx, wy, 0.0)
            lx, ly = int(lx), int(ly)
            d2 = (xx - lx) ** 2 + (yy - ly) ** 2
            fall = np.clip(1.0 - np.sqrt(d2) / rpx, 0.0, 1.0) ** 2
            lum = lum + fall * inten
        lum = np.clip(lum, 0.0, 1.0)
        arr = np.stack([
            (lum * 255).astype(np.uint8),
            (lum * 248).astype(np.uint8),
            (lum * 220).astype(np.uint8),
        ], axis=2)
        if self._lightmap is None or \
                self._lightmap.get_size() != (W, H):
            self._lightmap = pygame.surfarray.make_surface(
                np.transpose(arr, (1, 0, 2)))
        else:
            pygame.surfarray.blit_array(self._lightmap,
                                        np.transpose(arr, (1, 0, 2)))
        self.screen.blit(self._lightmap, (0, 0),
                         special_flags=pygame.BLEND_RGB_MULT)

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

