import logging
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
import tifffile


def test_logger():
    log = logging.getLogger("startrail_test")
    if not log.handlers:
        log.addHandler(logging.NullHandler())
    return log


def synthetic_frame(width=64, height=64, seed=0, value=None):
    rng = np.random.default_rng(seed)
    if value is not None:
        arr = np.full((height, width, 3), value, dtype=np.uint16)
    else:
        arr = rng.integers(0, 2048, (height, width, 3), dtype=np.uint16)
    return arr


def save_tiff(arr, path):
    tifffile.imwrite(str(path), arr, compression=None)
    return path


def make_project(tmp_path, name="testproj"):
    from startrail_pipeline.commands.init_ import cmd_init

    project = tmp_path / name

    class Args:
        pass

    args = Args()
    args.project = project
    args.force = False
    args.verbose = 0

    cmd_init(args, test_logger())
    return project
