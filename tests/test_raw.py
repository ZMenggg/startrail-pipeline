import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image
import tifffile

from startrail_pipeline.commands.develop_ import developed_path
from startrail_pipeline.commands.develop_ import cmd_develop
from startrail_pipeline.commands.run_ import ensure_analysis_available
from startrail_pipeline.config import DEFAULT_CONFIG
from startrail_pipeline.manifest import read_manifest, write_manifest
from startrail_pipeline.raw_backend import (
    generate_raw_preview,
    validate_developed_tiff,
)
from tests.conftest import make_project


class TestRawWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.log = logging.getLogger("raw-test")
        self.log.addHandler(logging.NullHandler())

    def test_developed_path_preserves_relative_directories(self):
        project = self.tmp / "project"
        first = {"path": "/a/frame.raw", "relative_path": "camera-a/frame.raw"}
        second = {"path": "/b/frame.raw", "relative_path": "camera-b/frame.raw"}
        self.assertNotEqual(
            developed_path(project, first),
            developed_path(project, second),
        )
        self.assertEqual(
            developed_path(project, first),
            project / "developed/camera-a/frame.tif",
        )

    def test_validate_developed_tiff_rejects_truncated_file(self):
        valid_path = self.tmp / "valid.tif"
        broken_path = self.tmp / "broken.tif"
        tifffile.imwrite(
            valid_path,
            np.zeros((8, 8, 3), dtype=np.uint16),
        )
        broken_path.write_bytes(b"II")
        self.assertTrue(validate_developed_tiff(valid_path)[0])
        self.assertFalse(validate_developed_tiff(broken_path)[0])

    def test_generate_raw_preview_uses_embedded_image(self):
        source = self.tmp / "frame.raf"
        output = self.tmp / "frame.jpg"
        source.write_bytes(b"synthetic raw placeholder")
        embedded = Image.new("RGB", (1200, 800), "black")
        with mock.patch(
            "startrail_pipeline.raw_backend._embedded_preview",
            return_value=embedded,
        ):
            result = generate_raw_preview(
                source, output, 256, DEFAULT_CONFIG, self.log
            )
        self.assertTrue(result)
        with Image.open(output) as image:
            self.assertLessEqual(max(image.size), 256)

    def test_missing_raw_proxy_blocks_automatic_run(self):
        with self.assertRaisesRegex(RuntimeError, "no usable preview"):
            ensure_analysis_available(
                [{"anomalies": ["proxy_missing"], "path": "frame.raf"}]
            )

    def test_develop_quarantines_corrupt_output_and_rebuilds(self):
        project = make_project(self.tmp)
        source = self.tmp / "frame.raf"
        source.write_bytes(b"raw data")
        record = {
            "path": str(source),
            "relative_path": "frame.raf",
            "decision": "keep",
            "override": False,
        }
        write_manifest(project, "selection", [record])
        destination = developed_path(project, record)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"II")

        def fake_develop(src, dst, log):
            tifffile.imwrite(
                dst,
                np.zeros((8, 8, 3), dtype=np.uint16),
            )

        args = type(
            "Args",
            (),
            {
                "project": project,
                "style": None,
                "raw_backend": "rawpy",
                "force": False,
            },
        )()
        with mock.patch(
            "startrail_pipeline.commands.develop_.choose_raw_backend",
            return_value=("rawpy", None),
        ), mock.patch(
            "startrail_pipeline.commands.develop_._develop_with_rawpy",
            side_effect=fake_develop,
        ):
            cmd_develop(args, self.log)

        self.assertTrue(validate_developed_tiff(destination)[0])
        quarantined = list((destination.parent / "quarantine").iterdir())
        self.assertEqual(len(quarantined), 1)
        report = read_manifest(project, "development")
        self.assertEqual(report[0]["status"], "developed")


if __name__ == "__main__":
    unittest.main()
