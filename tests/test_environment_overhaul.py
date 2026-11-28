"""Regression tests for the expanded forest and physical tree barriers."""
from __future__ import annotations

import unittest

import config
from systems.navigation import Navigation
from world.map_generator import build_world


class ExpandedEnvironmentTests(unittest.TestCase):
    def test_world_is_expanded_and_seeded(self):
        first = build_world(seed=73)
        second = build_world(seed=73)
        self.assertEqual((first.W, first.H), (96, 96))
        self.assertEqual(first.tiles, second.tiles)
        self.assertEqual(first.blocks, second.blocks)
        self.assertGreater(len(first.obstacles_of("tree")), 700)
        self.assertGreater(len(first.obstacles_of("bush")), 100)
        self.assertGreater(len(first.obstacles_of("fallen_log")), 30)

    def test_main_trail_connects_start_to_shrine(self):
        world = build_world(seed=12)
        nav = Navigation(world.grid, world.W, world.H)
        path = nav.a_star(world.start, world.shrine)
        self.assertIsNotNone(path)
        self.assertGreater(len(path), 20)
        self.assertEqual(path[0], world.start)
        self.assertEqual(path[-1], world.shrine)

    def test_tree_trunks_are_solid_but_use_round_collision(self):
        world = build_world(seed=99)
        tree = world.obstacles_of("tree")[0]
        tx, ty = int(tree.x), int(tree.y)
        self.assertTrue(world.grid.is_blocked(tx, ty))
        radius = world.grid.circle_blocks[(tx, ty)]
        center = (tx + 0.5, ty + 0.5)
        blocked = world.grid.resolve_circle(center, config.PLAYER_RADIUS)
        self.assertGreater(
            ((blocked[0] - center[0]) ** 2 +
             (blocked[1] - center[1]) ** 2) ** 0.5, 0.0)
        near = (center[0] + radius + config.PLAYER_RADIUS + 0.04, center[1])
        resolved = world.grid.resolve_circle(near, config.PLAYER_RADIUS)
        self.assertAlmostEqual(resolved[0], near[0], places=6)
        self.assertAlmostEqual(resolved[1], near[1], places=6)

    def test_height_field_is_smooth_and_non_flat(self):
        world = build_world(seed=8)
        values = [world.height_at(x, y) for x, y in
                  ((8, 8), (24, 18), (48, 48), (76, 80))]
        self.assertGreater(max(values) - min(values), 0.12)
        self.assertLess(max(abs(a - b) for a, b in
                            zip(values, values[1:])), 1.5)

    def test_obstacle_culling_matches_full_scan(self):
        world = build_world(seed=21)
        bounds = (30.0, 35.0, 48.0, 55.0)
        expected = [o for o in world.obstacles
                    if o.in_rect(*bounds, pad=1.5)]
        actual = world.cull_obstacles(*bounds, pad=1.5)
        self.assertEqual({id(o) for o in actual},
                         {id(o) for o in expected})

    def test_all_enemy_spawn_points_are_clear_and_reachable(self):
        world = build_world(seed=91)
        nav = Navigation(world.grid, world.W, world.H)
        self.assertGreaterEqual(len(world.spawn_points), 8)
        for point in world.spawn_points:
            self.assertFalse(world.grid.is_blocked(*point))
            self.assertIsNotNone(nav.a_star(point, world.shrine))

    def test_height_queries_are_safe_at_map_edges(self):
        world = build_world(seed=8)
        for x, y in ((0, 0), (95.5, 0), (0, 95.5), (95.5, 95.5)):
            self.assertTrue(-0.28 <= world.height_at(x, y) <= 1.05)

    def test_paths_remain_clear_of_tree_barriers(self):
        world = build_world(seed=44)
        for y, row in enumerate(world.tiles):
            for x, tile in enumerate(row):
                if tile == config.T_PATH:
                    self.assertNotEqual(world.blocks[y][x], config.BLOCK_TREE)


if __name__ == "__main__":
    unittest.main()
