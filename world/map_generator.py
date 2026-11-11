"""Build a fully populated :class:`world.environment.World`."""
from __future__ import annotations

from world.environment import World
from world.map_data import generate_map


def build_world(seed: int = 1234) -> World:
    """Generate and wrap the forest-shrine map into a World object."""
    data = generate_map(seed)
    world = World(data)
    return world
