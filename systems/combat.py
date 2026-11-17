"""Combat system: firing, projectile-vs-enemy hits and impacts."""
from __future__ import annotations

from typing import List

import config
from entities.bullet import Bullet


class CombatSystem:
    def __init__(self, grid) -> None:
        self.grid = grid
        self.bullets: List[Bullet] = []
        self._last_shot_audio = None
        self.grenades = []
        self._melee_cooldown = 0.0
        self._melee_requested = False

    # ------------------------------------------------------------------
    def fire(self, player, aim_dir, audio, particles) -> bool:
        w = player.weapon
        params = w.try_fire()
        if params is None:
            if w.is_empty():
                if w.start_reload():
                    if audio:
                        audio.play("reload")
            return False
        # spawn pellets from just in front of the player
        ox = player.x + aim_dir[0] * 0.6
        oy = player.y + aim_dir[1] * 0.6
        for _ in range(params["pellets"]):
            b = Bullet(
                ox, oy, aim_dir,
                params["speed"], params["damage"], params["range"],
                w.spec["color"], pellets=params["pellets"],
                spread=params["spread"])
            self.bullets.append(b)
        player.mark_shoot()
        if audio:
            key = "shot_" + w.kind
            if key in getattr(audio, "sfx", {}):
                audio.play(key)
        if particles:
            particles.emit("muzzle", ox, oy, 0.5,
                           aim_dir[0] * 1.5, aim_dir[1] * 1.5, 0.5,
                           0.06, (255, 220, 150), 8)
        return True

    # ------------------------------------------------------------------
    def request_melee(self, player) -> None:
        if self._melee_cooldown > 0.0:
            return
        self._melee_origin = (player.x, player.y)
        self._melee_aim = player.aim
        self._melee_requested = True

    def throw_grenade(self, player, aim_dir) -> bool:
        if len(self.grenades) >= 4:
            return False
        self.grenades.append({"x": player.x + aim_dir[0] * 0.55,
            "y": player.y + aim_dir[1] * 0.55, "vx": aim_dir[0] * 7.0,
            "vy": aim_dir[1] * 7.0, "fuse": 1.35, "age": 0.0})
        return True

    # ------------------------------------------------------------------
    def update(self, dt: float, zombies: List, particles, audio) -> List:
        """Advance bullets; return the list of zombies that just died."""
        killed = []
        self._melee_cooldown = max(0.0, self._melee_cooldown - dt)
        if self._melee_requested and self._melee_cooldown <= 0.0:
            self._melee_cooldown = 0.48
            px, py = self._melee_origin
            ax, ay = self._melee_aim
            for z in zombies:
                if not z.alive or getattr(z, "spawning", False):
                    continue
                dx, dy = z.x - px, z.y - py
                dist = (dx * dx + dy * dy) ** 0.5
                dot = (dx * ax + dy * ay) / max(0.001, dist)
                if dist <= 1.45 and dot >= 0.15:
                    z.on_hit(48.0, None, knock_dir=(dx, dy))
                    if particles:
                        particles.burst("blood", z.x, z.y, 0.4, 9, (130, 40, 30), speed=1.4, life=0.55, upward=True)
                    if audio:
                        audio.play("zombie_hit")
                    if not z.alive:
                        killed.append(z)
        self._melee_requested = False
        for b in self.bullets:
            b.update(dt)
            tx = int(b.x)
            ty = int(b.y)
            # hit a solid obstacle (tree / rock) -> impact spark
            if not self.grid.in_bounds(tx, ty):
                b.active = False
                continue
            if self.grid.blocks[ty][tx] == config.BLOCK_SOLID:
                b.active = False
                if particles:
                    particles.burst("spark", b.x, b.y, 0.35, 5,
                                    (200, 180, 120), speed=1.0,
                                    life=0.35, size=2.0)
                continue
            # hit a zombie
            for z in zombies:
                if not z.alive or getattr(z, "spawning", False):
                    continue
                dx = b.x - z.x
                dy = b.y - z.y
                rr = z.radius + 0.15
                if dx * dx + dy * dy < rr * rr:
                    # Knock the zombie away from the shot (direction-aware).
                    m = (dx * dx + dy * dy) ** 0.5 or 1.0
                    # Headshot: near-center hits deal bonus damage.
                    center_ratio = ((dx * dx + dy * dy) ** 0.5) / max(0.01, rr)
                    dmg = b.damage * (1.6 if center_ratio < 0.45 else 1.0)
                    z.on_hit(dmg, b, knock_dir=(-dx / m, -dy / m))
                    b.active = False
                    if particles:
                        particles.burst(
                            "blood", z.x, z.y, 0.4, 10 if center_ratio < 0.45 else 8,
                            (130, 40, 30), speed=1.5, life=0.6,
                            upward=True)
                    if audio:
                        audio.play("zombie_hit")
                    if not z.alive:
                        killed.append(z)
                    break
        self.bullets = [b for b in self.bullets if b.active]
        active_grenades = []
        for g in self.grenades:
            g["age"] += dt
            g["fuse"] -= dt
            if g["age"] < 0.55:
                nx, ny = g["x"] + g["vx"] * dt, g["y"] + g["vy"] * dt
                tx, ty = int(nx), int(ny)
                if self.grid.in_bounds(tx, ty) and self.grid.blocks[ty][tx] != config.BLOCK_SOLID:
                    g["x"], g["y"] = nx, ny
                g["vx"] *= max(0.0, 1.0 - 2.2 * dt)
                g["vy"] *= max(0.0, 1.0 - 2.2 * dt)
            if g["fuse"] <= 0.0:
                for z in zombies:
                    if not z.alive or getattr(z, "spawning", False):
                        continue
                    dx, dy = z.x - g["x"], z.y - g["y"]
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist <= 3.2:
                        z.on_hit(105.0 * (1.0 - 0.65 * dist / 3.2), None, knock_dir=(dx, dy))
                        if not z.alive:
                            killed.append(z)
                if particles:
                    particles.burst("spark", g["x"], g["y"], 0.8, 34, (255, 155, 65), speed=3.0, life=0.8, size=4.0)
                    particles.burst("smoke", g["x"], g["y"], 0.5, 18, (90, 85, 75), speed=1.0, life=1.0, size=5.0)
                if audio:
                    audio.play("explosion")
            else:
                active_grenades.append(g)
        self.grenades = active_grenades
        return killed

    def clear(self) -> None:
        self.bullets = []
        self.grenades = []
