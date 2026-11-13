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
    def update(self, dt: float, zombies: List, particles, audio) -> List:
        """Advance bullets; return the list of zombies that just died."""
        killed = []
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
                    z.on_hit(dmg, b, knock_dir=dx / m)
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
        return killed

    def clear(self) -> None:
        self.bullets = []
