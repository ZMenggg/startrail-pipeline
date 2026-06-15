import unittest
import tempfile
from pathlib import Path
from tests.conftest import synthetic_frame, save_tiff, make_project, test_logger
from startrail_pipeline.commands.inventory_ import cmd_inventory
from startrail_pipeline.commands.analyze_ import cmd_analyze
from startrail_pipeline.commands.select_ import cmd_select
from startrail_pipeline.manifest import read_manifest


class TestSelect(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "source"
        self.source.mkdir()
        self.project = make_project(self.tmp)
        self.log = test_logger()

    def test_select_keep_all_when_no_anomalies(self):
        for i in range(3):
            arr = synthetic_frame(seed=i)
            save_tiff(arr, self.source / f"frame_{i:04d}.tif")

        i_args = type("Args", (), {
            "project": self.project, "source": self.source, "verbose": 0
        })()
        cmd_inventory(i_args, self.log)

        a_args = type("Args", (), {"project": self.project, "verbose": 0})()
        cmd_analyze(a_args, self.log)

        s_args = type("Args", (), {
            "project": self.project, "override": None, "verbose": 0
        })()
        cmd_select(s_args, self.log)

        selection = read_manifest(self.project, "selection")
        self.assertEqual(len(selection), 3)
        self.assertTrue(all(s["decision"] == "keep" for s in selection))

    def test_override_csv_takes_priority(self):
        for i in range(2):
            arr = synthetic_frame(seed=i)
            save_tiff(arr, self.source / f"frame_{i:04d}.tif")

        i_args = type("Args", (), {
            "project": self.project, "source": self.source, "verbose": 0
        })()
        cmd_inventory(i_args, self.log)

        inventory = read_manifest(self.project, "inventory")
        override_csv = self.tmp / "override.csv"
        rel = inventory[0].get("relative_path", "frame_0000.tif")
        override_csv.write_text(f"relative_path,decision\n{rel},reject_candidate\n")

        a_args = type("Args", (), {"project": self.project, "verbose": 0})()
        cmd_analyze(a_args, self.log)

        s_args = type("Args", (), {
            "project": self.project, "override": override_csv, "verbose": 0
        })()
        cmd_select(s_args, self.log)

        selection = read_manifest(self.project, "selection")
        overridden = [s for s in selection if s["override"]]
        self.assertEqual(len(overridden), 1)
        self.assertEqual(overridden[0]["decision"], "reject_candidate")


if __name__ == "__main__":
    unittest.main()
