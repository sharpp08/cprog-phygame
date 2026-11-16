"""Headless regression tests for the world-space cloud simulation."""
import unittest

from systems.clouds import CloudField


class CloudFieldTests(unittest.TestCase):
    def test_clouds_move_without_camera_motion(self):
        field = CloudField(count=4, seed=7)
        field.initialize(40.0, 40.0)
        before = [(c.x, c.y) for c in field.clouds]
        field.update(1.0, 40.0, 40.0, wind=0.0, wind_dir=1.0)
        after = [(c.x, c.y) for c in field.clouds]
        self.assertTrue(any(a != b for a, b in zip(before, after)))

    def test_clouds_are_not_wrapped_to_map_dimensions(self):
        field = CloudField(count=1, seed=3)
        field.initialize(50.0, 50.0)
        cloud = field.clouds[0]
        cloud.x = 110.0
        cloud.y = 50.0
        field.update(0.01, 50.0, 50.0, wind=0.0, wind_dir=1.0)
        self.assertGreater(cloud.x, 100.0)

    def test_camera_motion_does_not_modify_cloud_world_positions(self):
        first = CloudField(count=6, seed=19)
        second = CloudField(count=6, seed=19)
        first.initialize(40.0, 40.0)
        second.initialize(40.0, 40.0)
        first.update(0.5, 40.0, 40.0, wind=0.2, wind_dir=1.0)
        second.update(0.5, 41.0, 40.0, wind=0.2, wind_dir=1.0)
        for a, b in zip(first.clouds, second.clouds):
            self.assertAlmostEqual(a.x, b.x)
            self.assertAlmostEqual(a.y, b.y)


if __name__ == "__main__":
    unittest.main()
