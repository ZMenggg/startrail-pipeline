import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import tifffile


class TestBatchScript(unittest.TestCase):
    def test_complete_batch_uses_isolated_photo_root(self):
        root = Path(__file__).resolve().parents[1]
        photo_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, photo_root, True)
        input_dir = photo_root / "input"
        input_dir.mkdir()

        for index in range(3):
            array = np.zeros((16, 16, 3), dtype=np.uint16)
            array[4 + index, 2:12] = 10000
            tifffile.imwrite(input_dir / f"frame_{index:02d}.tif", array)

        env = os.environ.copy()
        env["STARTRAIL_PHOTO_ROOT"] = str(photo_root)
        env["STARTRAIL_PYTHON"] = sys.executable
        result = subprocess.run(
            ["/bin/sh", str(root / "process_photo_batch.sh"), "test-batch"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        batches = list((photo_root / "completed").iterdir())
        self.assertEqual(len(batches), 1)
        batch = batches[0]
        self.assertEqual((batch / "STATUS.txt").read_text().strip(), "complete")
        self.assertTrue((batch / "startrail.tif").exists())
        self.assertTrue((batch / "preview.jpg").exists())
        self.assertTrue((batch / "review.html").exists())
        self.assertTrue((batch / "selection.csv").exists())


if __name__ == "__main__":
    unittest.main()
