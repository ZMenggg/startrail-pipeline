import unittest

import numpy as np

from startrail_pipeline.commands.gap_fill_ import gap_fill_image


class TestGapFill(unittest.TestCase):
    def test_fills_gap_along_direction_and_preserves_foreground(self):
        image = np.zeros((12, 8, 3), dtype=np.uint16)
        image[1, 2] = 20000
        image[7, 4] = 20000
        image[10:, :] = 5000

        result = gap_fill_image(image, dx=1, dy=3, sky_fraction=0.75)

        self.assertGreater(result[4, 3, 0], 0)
        self.assertTrue(np.array_equal(result[10:], image[10:]))


if __name__ == "__main__":
    unittest.main()
