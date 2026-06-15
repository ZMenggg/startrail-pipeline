import unittest
import tempfile
from pathlib import Path
from startrail_pipeline.commands.doctor_ import (
    _check_python,
    _check_dep,
)


class TestDoctor(unittest.TestCase):
    def test_python_version_ok(self):
        ok, msg = _check_python()
        self.assertTrue(ok)
        self.assertIn("Python", msg)

    def test_numpy_found(self):
        ok, msg = _check_dep("numpy")
        self.assertTrue(ok)

    def test_pillow_found(self):
        ok, msg = _check_dep("Pillow", import_name="PIL")
        self.assertTrue(ok)

    def test_tifffile_found(self):
        ok, msg = _check_dep("tifffile")
        self.assertTrue(ok)

    def test_fake_dep_not_found(self):
        ok, msg = _check_dep("nonexistent_package_xyz")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
