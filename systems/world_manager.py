"""Creates the live world objects: terrain, pickups and initial zombies."""
from __future__ import annotations

import random
from typing import List

from entities.pickup import Pickup
from entities.zombie import Zombie
from systems.enemy_ai import ZombieController
from systems.navigation import Navigation
from world.environment import World


class WorldManager:
    def __init__(self, seed: int = 1234) -> None:
        from world.map_generator import build_world
        self.world: World = build_world(seed)
        self.grid = self.world.grid
        self.nav = Navigation(self.grid, self.world.W, self.world.H)
        self.controller = ZombieController(self.grid, self.nav,
                                            self.world.W, self.world.H)
        self.pickups: List[Pickup] = \
            [Pickup(x, y, p) for (x, y, p) in self.world.loot]

    # ------------------------------------------------------------------
    def setup(self, player, audio, particles) -> None:
        self.controller.set_context(player, audio, particles,
                                    self.world.spawn_points)
        # a few initial zombies scattered around the map
        for i in range(6):
            x, y = self._random_clear_tile()
            zt = random.choice(["regular", "regular", "fast"])
            z = self.controller.add_zombie(None, x, y, zt)
            z.path = self.nav.a_star((int(x), int(y)),
                                     (int(player.x), int(player.y)))
            z.path_i = 0

    def _random_clear_tile(self):
        g = self.world.grid
        for _ in range(40):
            x = random.randint(2, self.world.W - 3)
            y = random.randint(2, self.world.H - 3)
            if g.is_blocked(x, y):
                continue
            return float(x), float(y)
        return float(self.world.start[0]), float(self.world.start[1])

    # ------------------------------------------------------------------
    def player_pickup_zone(self, player) -> List[Pickup]:
        return [p for p in self.pickups
                if not p.taken and p.overlap(player)]

    def active_pickups(self) -> List[Pickup]:
        return [p for p in self.pickups if not p.taken]
