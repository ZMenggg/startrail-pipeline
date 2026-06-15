import io
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import tifffile


DARKTABLE_APP_CLI = Path(
    "/Applications/darktable.app/Contents/MacOS/darktable-cli"
)


def find_darktable(config=None):
    raw_config = (config or {}).get("raw_developer", {})
    configured = raw_config.get("executable", "")
    candidates = [
        configured,
        os.environ.get("STARTRAIL_DARKTABLE_CLI", ""),
        shutil.which("darktable-cli") or "",
        str(DARKTABLE_APP_CLI),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def has_rawpy():
    try:
        import rawpy  # noqa: F401
    except ImportError:
        return False
    return True


def probe_darktable(path, timeout=10):
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout} seconds"
    except OSError as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return False, detail or f"exited with status {result.returncode}"
    version_lines = (result.stdout or result.stderr).strip().splitlines()
    return True, version_lines[0] if version_lines else "version unknown"


def choose_raw_backend(config, requested="auto"):
    configured = config.get("raw_developer", {}).get("backend", "auto")
    backend = requested if requested and requested != "auto" else configured
    backend = backend or "auto"
    darktable = find_darktable(config)

    if backend == "darktable":
        if not darktable:
            raise RuntimeError(
                "darktable-cli was requested but was not found. Set "
                "raw_developer.executable in project.toml or "
                "STARTRAIL_DARKTABLE_CLI."
            )
        ok, reason = probe_darktable(darktable)
        if not ok:
            raise RuntimeError(f"darktable-cli is not usable: {reason}")
        return "darktable", darktable
    if backend == "rawpy":
        if not has_rawpy():
            raise RuntimeError(
                "rawpy was requested but is not installed. Install with "
                "'python -m pip install -e .[raw]'."
            )
        return "rawpy", None
    if backend != "auto":
        raise RuntimeError(f"Unsupported RAW backend: {backend}")

    if darktable:
        ok, _ = probe_darktable(darktable)
        if ok:
            return "darktable", darktable
    if has_rawpy():
        return "rawpy", None
    raise RuntimeError(
        "No RAW developer is available. Install darktable, install the "
        "'raw' extra, or configure raw_developer.executable."
    )


def _embedded_preview(src):
    exiftool = shutil.which("exiftool")
    if not exiftool:
        return None
    for tag in ("PreviewImage", "JpgFromRaw", "ThumbnailImage"):
        try:
            result = subprocess.run(
                [exiftool, "-b", f"-{tag}", str(src)],
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 or not result.stdout:
            continue
        try:
            with Image.open(io.BytesIO(result.stdout)) as image:
                return ImageOps.exif_transpose(image).convert("RGB")
        except Exception:
            continue
    return None


def generate_raw_preview(src, dst, max_size, config, log):
    image = _embedded_preview(src)
    method = "embedded preview"

    if image is None and has_rawpy():
        import rawpy

        with rawpy.imread(str(src)) as raw:
            array = raw.postprocess(
                output_bps=8,
                use_camera_wb=True,
                half_size=True,
                no_auto_bright=False,
            )
        image = Image.fromarray(array, "RGB")
        method = "rawpy"

    if image is None:
        log.warning(f"Cannot generate RAW preview for {src}")
        return False

    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    temporary = dst.with_name(f".{dst.name}.partial")
    image.save(temporary, "JPEG", quality=85)
    os.replace(temporary, dst)
    log.debug(f"RAW preview generated with {method}: {src.name}")
    return True


def validate_developed_tiff(path):
    try:
        with tifffile.TiffFile(path) as tif:
            if len(tif.pages) != 1:
                return False, "expected one TIFF page"
            page = tif.pages[0]
            shape = page.shape
            if page.dtype != np.dtype(np.uint16):
                return False, f"expected uint16, got {page.dtype}"
            if len(shape) != 3 or shape[2] < 3 or min(shape[:2]) <= 0:
                return False, f"expected RGB image, got shape {shape}"
    except Exception as exc:
        return False, str(exc)
    return True, ""
