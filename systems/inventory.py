"""Item / pickup application: turning ground loot into player changes."""
from __future__ import annotations

from entities.pickup import Pickup
from entities.player import Player
from entities.weapon import Weapon


def apply_pickup(player: Player, pickup: Pickup, audio=None, survival=None) -> None:
    ptype = pickup.ptype
    spec = pickup.spec
    if ptype.startswith("ammo"):
        kind = ptype.split("_", 1)[1]
        target = None
        for w in player.weapons:
            if w.kind == kind:
                target = w
                break
        if target is None:
            target = Weapon(kind)
            player.add_weapon(target)
        target.add_reserve(pickup.value)
    elif ptype == "battery" and survival is not None:
        survival.add_battery_cells(pickup.value)
    elif ptype == "medkit" and survival is not None:
        survival.medkits = min(9, survival.medkits + 1)
    elif ptype == "grenade" and survival is not None:
        survival.add_grenades(pickup.value)
    elif ptype.startswith("weapon"):
        kind = ptype.split("_", 1)[1]
        if not player.has_weapon(kind):
            player.add_weapon(Weapon(kind))
    if audio:
        audio.play("pickup")
    pickup.taken = True
