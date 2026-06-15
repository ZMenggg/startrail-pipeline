import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import tifffile

from startrail_pipeline.config import read_config
from startrail_pipeline.manifest import read_manifest, write_manifest
from startrail_pipeline.raw_backend import (
    choose_raw_backend,
    validate_developed_tiff,
)


def _develop_with_rawpy(src, dst, log):
    """Develop RAW file using rawpy (LibRaw wrapper)."""
    import rawpy

    log.info(f"Developing {src.name} -> {dst.name} (rawpy)")
    with rawpy.imread(str(src)) as raw:
        rgb = raw.postprocess(
            output_bps=16,
            output_color=rawpy.ColorSpace.sRGB,
            no_auto_bright=True,
            use_camera_wb=True,
            highlight_mode=0,
            gamma=(1.0, 1.0),
        )
    tifffile.imwrite(str(dst), rgb, compression="zlib")


def _develop_with_darktable(executable, src, dst, style, log):
    """Develop RAW file using darktable-cli."""
    cmd = [str(executable), str(src), str(dst), "--out-ext", "tiff"]
    if style:
        cmd.extend(["--style", style])
    cmd.extend(
        [
            "--core",
            "--conf",
            "plugins/imageio/format/tiff/bpp=16",
            "--conf",
            "plugins/imageio/format/tiff/compress=1",
        ]
    )
    log.info(f"Developing {src.name} -> {dst.name} (darktable-cli)")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(
            f"darktable-cli failed for {src.name}: {result.stderr.strip()}"
        )
    return True


def developed_path(project, record):
    relative = Path(record.get("relative_path") or Path(record["path"]).name)
    return project / "developed" / relative.with_suffix(".tif")


def _quarantine_existing(path, log):
    quarantine = path.parent / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = quarantine / f"{path.name}.{stamp}.corrupt"
    path.replace(target)
    log.warning(f"Moved existing developed TIFF to {target}")


def _check_disk_space(project, records, config):
    remaining_source_bytes = 0
    for record in records:
        if record["decision"] != "keep":
            continue
        source = Path(record["path"])
        if source.suffix.lower() not in config["extensions"]["raw"]:
            continue
        destination = developed_path(project, record)
        valid = destination.exists() and validate_developed_tiff(destination)[0]
        if not valid:
            remaining_source_bytes += source.stat().st_size

    ratio = float(
        config["raw_developer"].get("estimated_tiff_size_ratio", 6.5)
    )
    reserve = float(config["raw_developer"].get("disk_reserve_gb", 10))
    estimated = int(remaining_source_bytes * ratio)
    free = shutil.disk_usage(project).free
    required = estimated + int(reserve * 1024**3)
    if free < required:
        raise RuntimeError(
            "Insufficient disk space for RAW development: approximately "
            f"{estimated / 1024**3:.1f} GB of TIFF data remains, "
            f"{free / 1024**3:.1f} GB is free, and {reserve:.1f} GB is reserved."
        )
    return estimated, free


def cmd_develop(args, log):
    selection = read_manifest(args.project, "selection")
    if not selection:
        log.warning("No selection found. Run 'select' first.")
        return

    config = read_config(args.project)
    style = args.style or config["raw_developer"].get("style_name")

    has_raw = any(
        rec["decision"] == "keep"
        and Path(rec["path"]).suffix.lower() in config["extensions"]["raw"]
        for rec in selection
    )
    if not has_raw:
        log.info("No selected RAW files require development.")
        return

    backend, executable = choose_raw_backend(
        config, getattr(args, "raw_backend", "auto")
    )
    if backend == "rawpy" and style:
        raise RuntimeError(
            "A darktable style was requested, but the selected backend is rawpy. "
            "Use --raw-backend darktable or remove the style."
        )
    log.info(f"RAW developer: {backend}")

    developed_dir = args.project / "developed"
    developed_dir.mkdir(parents=True, exist_ok=True)
    estimated, free = _check_disk_space(args.project, selection, config)
    log.info(
        f"RAW disk estimate: {estimated / 1024**3:.1f} GB remaining; "
        f"{free / 1024**3:.1f} GB free"
    )

    development_records = []
    for rec in selection:
        if rec["decision"] != "keep":
            continue
        src = Path(rec["path"])
        if src.suffix.lower() not in config["extensions"]["raw"]:
            continue
        dst = developed_path(args.project, rec)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            valid, reason = validate_developed_tiff(dst)
            if valid and not getattr(args, "force", False):
                log.info(f"Already developed and valid: {dst.name}")
                development_records.append(
                    {
                        "source_path": str(src),
                        "relative_path": rec.get("relative_path", src.name),
                        "output_path": str(dst),
                        "backend": backend,
                        "status": "existing_valid",
                        "output_size": dst.stat().st_size,
                    }
                )
                continue
            if valid:
                _quarantine_existing(dst, log)
            else:
                log.warning(f"Invalid developed TIFF {dst}: {reason}")
                _quarantine_existing(dst, log)

        temporary = dst.with_name(f".{dst.stem}.partial.tif")
        temporary.unlink(missing_ok=True)
        if backend == "darktable":
            _develop_with_darktable(executable, src, temporary, style, log)
        else:
            _develop_with_rawpy(src, temporary, log)
        valid, reason = validate_developed_tiff(temporary)
        if not valid:
            raise RuntimeError(f"RAW developer produced an invalid TIFF: {reason}")
        os.replace(temporary, dst)
        development_records.append(
            {
                "source_path": str(src),
                "relative_path": rec.get("relative_path", src.name),
                "output_path": str(dst),
                "backend": backend,
                "status": "developed",
                "output_size": dst.stat().st_size,
            }
        )
        if len(development_records) % 25 == 0:
            write_manifest(args.project, "development", development_records)

    write_manifest(args.project, "development", development_records)
    log.info(f"RAW development complete: {len(development_records)} frame(s)")
