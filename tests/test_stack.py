import unittest
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
import tifffile
from tests.conftest import synthetic_frame, save_tiff, make_project, test_logger
from startrail_pipeline.commands.stack_ import (
    _sequence_signature,
    _write_checkpoint,
    cmd_stack,
)
from startrail_pipeline.config import read_config
from startrail_pipeline.manifest import write_manifest


def _make_selection(project, paths):
    records = []
    for p in paths:
        records.append({
            "path": str(p),
            "relative_path": p.name,
            "decision": "keep",
            "override": False,
        })
    write_manifest(project, "selection", records)


class TestStack(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = make_project(self.tmp)
        self.log = test_logger()

    def test_basic_maximum_stack(self):
        frames = []
        arr0 = np.zeros((16, 16, 3), dtype=np.uint16)
        arr0[:, :8] = 1000
        arr1 = np.zeros((16, 16, 3), dtype=np.uint16)
        arr1[:, 8:] = 2000

        for i, arr in enumerate([arr0, arr1]):
            path = self.tmp / f"f{i}.tif"
            save_tiff(arr, path)
            frames.append(path)

        _make_selection(self.project, frames)

        args = type("Args", (), {
            "project": self.project, "mask": None, "resume": False, "verbose": 0
        })()
        cmd_stack(args, self.log)

        stack_path = self.project / "stacks" / "stack.tif"
        self.assertTrue(stack_path.exists())
        result = tifffile.imread(str(stack_path))
        self.assertEqual(result[0, 0, 0], 1000)
        self.assertEqual(result[0, 12, 0], 2000)

    def test_dimension_mismatch_raises_error(self):
        arr0 = synthetic_frame(64, 64, seed=0)
        arr1 = synthetic_frame(32, 32, seed=1)

        p0 = self.tmp / "f0.tif"
        p1 = self.tmp / "f1.tif"
        save_tiff(arr0, p0)
        save_tiff(arr1, p1)

        _make_selection(self.project, [p0, p1])

        args = type("Args", (), {
            "project": self.project, "mask": None, "resume": False, "verbose": 0
        })()
        with self.assertRaises(RuntimeError):
            cmd_stack(args, self.log)

    def test_mask_only_updates_sky_region(self):
        h, w = 16, 16
        black = np.zeros((h, w, 3), dtype=np.uint16)
        white = np.full((h, w, 3), 30000, dtype=np.uint16)
        mask_arr = np.zeros((h, w), dtype=np.uint16)
        mask_arr[:, :8] = 65535

        p_black = self.tmp / "black.tif"
        p_white = self.tmp / "white.tif"
        p_mask = self.tmp / "mask.tif"
        save_tiff(black, p_black)
        save_tiff(white, p_white)
        tifffile.imwrite(str(p_mask), mask_arr)

        _make_selection(self.project, [p_black, p_white])

        args = type("Args", (), {
            "project": self.project, "mask": p_mask, "resume": False, "verbose": 0
        })()
        cmd_stack(args, self.log)

        result = tifffile.imread(str(self.project / "stacks" / "stack.tif"))
        self.assertGreater(result[0, 0, 0], 0)
        self.assertEqual(result[0, 12, 0], 0)

    def test_checkpoint_resume(self):
        frames = []
        arrays = []
        for i in range(10):
            arr = synthetic_frame(16, 16, seed=i)
            path = self.tmp / f"f{i:02d}.tif"
            save_tiff(arr, path)
            frames.append(path)
            arrays.append(arr)

        _make_selection(self.project, frames)
        partial = np.maximum.reduce(arrays[:4])
        _write_checkpoint(
            self.project,
            partial,
            next_index=4,
            frame_count=4,
            signature=_sequence_signature(frames, None),
            config=read_config(self.project),
        )

        args2 = type("Args", (), {
            "project": self.project, "mask": None, "resume": True, "verbose": 0
        })()
        cmd_stack(args2, self.log)

        full = tifffile.imread(str(self.project / "stacks" / "stack.tif"))
        self.assertTrue(np.array_equal(full, np.maximum.reduce(arrays)))
        self.assertFalse((self.project / "stacks" / "_checkpoint.tif").exists())
        self.assertFalse((self.project / "stacks" / "_checkpoint.json").exists())

    def test_no_frames_does_nothing(self):
        _make_selection(self.project, [])

        args = type("Args", (), {
            "project": self.project, "mask": None, "resume": False, "verbose": 0
        })()
        cmd_stack(args, self.log)
        stack_path = self.project / "stacks" / "stack.tif"
        self.assertFalse(stack_path.exists())

    def test_png_input_is_supported(self):
        arr0 = np.zeros((8, 8, 3), dtype=np.uint8)
        arr1 = np.zeros((8, 8, 3), dtype=np.uint8)
        arr0[:, :4] = 10
        arr1[:, 4:] = 20
        p0 = self.tmp / "f0.png"
        p1 = self.tmp / "f1.png"
        Image.fromarray(arr0).save(p0)
        Image.fromarray(arr1).save(p1)
        _make_selection(self.project, [p0, p1])

        args = type("Args", (), {
            "project": self.project, "mask": None, "resume": False,
            "force": False, "verbose": 0
        })()
        cmd_stack(args, self.log)
        result = tifffile.imread(str(self.project / "stacks" / "stack.tif"))
        self.assertEqual(result[0, 0, 0], 10 * 257)
        self.assertEqual(result[0, 6, 0], 20 * 257)

    def test_existing_output_requires_force(self):
        arr = np.zeros((8, 8, 3), dtype=np.uint16)
        path = self.tmp / "frame.tif"
        save_tiff(arr, path)
        _make_selection(self.project, [path])
        args = type("Args", (), {
            "project": self.project, "mask": None, "resume": False,
            "force": False, "verbose": 0
        })()
        cmd_stack(args, self.log)
        with self.assertRaises(RuntimeError):
            cmd_stack(args, self.log)

    def test_resume_accepts_existing_completed_stack(self):
        arr = np.zeros((8, 8, 3), dtype=np.uint16)
        path = self.tmp / "frame.tif"
        save_tiff(arr, path)
        _make_selection(self.project, [path])
        first = type("Args", (), {
            "project": self.project, "mask": None, "resume": False,
            "force": False, "verbose": 0
        })()
        cmd_stack(first, self.log)
        output = self.project / "stacks" / "stack.tif"
        original_mtime = output.stat().st_mtime_ns

        resumed = type("Args", (), {
            "project": self.project, "mask": None, "resume": True,
            "force": False, "verbose": 0
        })()
        cmd_stack(resumed, self.log)
        self.assertEqual(output.stat().st_mtime_ns, original_mtime)


if __name__ == "__main__":
    unittest.main()
