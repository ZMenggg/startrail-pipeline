import unittest
import tempfile
from pathlib import Path
from tests.conftest import synthetic_frame, save_tiff, make_project, test_logger
from startrail_pipeline.commands.inventory_ import cmd_inventory
from startrail_pipeline.commands.analyze_ import cmd_analyze
from startrail_pipeline.manifest import read_manifest


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "source"
        self.source.mkdir()
        self.project = make_project(self.tmp)
        self.log = test_logger()

    def _run_inventory(self):
        class Args:
            pass
        args = Args()
        args.project = self.project
        args.source = self.source
        args.verbose = 0
        cmd_inventory(args, self.log)

    def test_analyze_on_empty_inventory(self):
        self._run_inventory()

        class Args:
            pass
        args = Args()
        args.project = self.project
        args.verbose = 0

        cmd_analyze(args, self.log)

    def test_analyze_marks_anomalies_with_mad(self):
        for i in range(5):
            arr = synthetic_frame(seed=i)
            save_tiff(arr, self.source / f"frame_{i:04d}.tif")

        bright_arr = synthetic_frame(seed=99)
        bright_arr[:] = 65535
        save_tiff(bright_arr, self.source / "frame_bright.tif")

        self._run_inventory()

        class Args:
            pass
        args = Args()
        args.project = self.project
        args.verbose = 0

        cmd_analyze(args, self.log)
        analysis = read_manifest(self.project, "analysis")
        self.assertGreater(len(analysis), 0)
        has_bright = any(a.get("clipped_ratio", 0) > 0 for a in analysis)
        self.assertTrue(has_bright)

    def test_analyze_generates_contact_sheet(self):
        for i in range(3):
            arr = synthetic_frame(seed=i)
            save_tiff(arr, self.source / f"frame_{i:04d}.tif")

        self._run_inventory()

        class Args:
            pass
        args = Args()
        args.project = self.project
        args.verbose = 0

        cmd_analyze(args, self.log)
        contact = self.project / "manifests" / "contact_sheet.html"
        self.assertTrue(contact.exists())
        content = contact.read_text()
        self.assertIn("<table>", content)


if __name__ == "__main__":
    unittest.main()
