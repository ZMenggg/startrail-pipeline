import unittest
import tempfile
from pathlib import Path
from unittest import mock
from tests.conftest import synthetic_frame, save_tiff, make_project, test_logger
from startrail_pipeline.commands.inventory_ import cmd_inventory
from startrail_pipeline.manifest import read_manifest


class TestInventory(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "source"
        self.source.mkdir()
        self.project = make_project(self.tmp)
        self.log = test_logger()

    def test_inventory_finds_tiff_files(self):
        for i in range(3):
            arr = synthetic_frame(seed=i)
            save_tiff(arr, self.source / f"frame_{i:04d}.tif")

        class Args:
            pass
        args = Args()
        args.project = self.project
        args.source = self.source
        args.verbose = 0

        cmd_inventory(args, self.log)
        manifest = read_manifest(self.project, "inventory")
        self.assertEqual(len(manifest), 3)

    def test_inventory_sorts_by_mtime_then_filename(self):
        for i in range(3):
            arr = synthetic_frame(seed=i)
            save_tiff(arr, self.source / f"pic_{i:04d}.tif")

        class Args:
            pass
        args = Args()
        args.project = self.project
        args.source = self.source
        args.verbose = 0

        cmd_inventory(args, self.log)
        manifest = read_manifest(self.project, "inventory")
        names = [Path(r["path"]).name for r in manifest]
        self.assertEqual(names, sorted(names))

    def test_inventory_computes_sha256(self):
        arr = synthetic_frame(seed=42)
        save_tiff(arr, self.source / "test.tif")

        class Args:
            pass
        args = Args()
        args.project = self.project
        args.source = self.source
        args.verbose = 0

        cmd_inventory(args, self.log)
        manifest = read_manifest(self.project, "inventory")
        self.assertEqual(len(manifest), 1)
        self.assertEqual(len(manifest[0]["sha256"]), 64)

    def test_inventory_empty_directory(self):
        class Args:
            pass
        args = Args()
        args.project = self.project
        args.source = self.source
        args.verbose = 0

        cmd_inventory(args, self.log)
        manifest = read_manifest(self.project, "inventory")
        self.assertEqual(manifest, [])

    def test_inventory_outputs_json_and_csv(self):
        arr = synthetic_frame(seed=0)
        save_tiff(arr, self.source / "frame.tif")

        class Args:
            pass
        args = Args()
        args.project = self.project
        args.source = self.source
        args.verbose = 0

        cmd_inventory(args, self.log)
        self.assertTrue((self.project / "manifests" / "inventory.json").exists())
        self.assertTrue((self.project / "manifests" / "inventory.csv").exists())

    def test_inventory_reuses_unchanged_hash(self):
        arr = synthetic_frame(seed=0)
        save_tiff(arr, self.source / "frame.tif")

        class Args:
            pass
        args = Args()
        args.project = self.project
        args.source = self.source
        args.verbose = 0

        cmd_inventory(args, self.log)
        with mock.patch(
            "startrail_pipeline.commands.inventory_._sha256",
            side_effect=AssertionError("hash should have been reused"),
        ):
            cmd_inventory(args, self.log)


if __name__ == "__main__":
    unittest.main()
