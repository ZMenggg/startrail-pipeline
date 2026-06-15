import hashlib
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import tifffile

from startrail_pipeline.config import read_config
from startrail_pipeline.commands.develop_ import developed_path
from startrail_pipeline.manifest import read_manifest, write_manifest


def _checkpoint_meta_path(project_path):
    return project_path / "stacks" / "_checkpoint.json"


def _checkpoint_image_path(project_path):
    return project_path / "stacks" / "_checkpoint.tif"


def _stack_path(project_path):
    return project_path / "stacks" / "stack.tif"


def _preview_path(project_path):
    return project_path / "stacks" / "preview.jpg"


def _normalize_rgb(arr, path):
    if arr.dtype == np.uint8:
        arr = arr.astype(np.uint16) * 257
    elif arr.dtype != np.uint16:
        raise ValueError(f"{path}: expected 8-bit or 16-bit integer pixels")
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.ndim != 3:
        raise ValueError(f"{path}: unsupported image shape {arr.shape}")
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    elif arr.shape[2] >= 3:
        arr = arr[:, :, :3]
    else:
        raise ValueError(f"{path}: unsupported channel count {arr.shape[2]}")
    return np.ascontiguousarray(arr)


def _load_frame(path):
    path = Path(path)
    if path.suffix.lower() in {".tif", ".tiff"}:
        arr = tifffile.imread(str(path))
    else:
        arr = np.asarray(ImageOps.exif_transpose(Image.open(path)).convert("RGB"))
    return _normalize_rgb(arr, path)


def _load_mask(path, shape):
    path = Path(path)
    if path.suffix.lower() in {".tif", ".tiff"}:
        mask = tifffile.imread(str(path))
    else:
        mask = np.asarray(Image.open(path).convert("L"))
    if mask.ndim == 3:
        mask = mask[:, :, 0]
    if mask.dtype == np.uint8:
        mask = mask.astype(np.uint16) * 257
    elif mask.dtype != np.uint16:
        raise ValueError(f"{path}: mask must be 8-bit or 16-bit")
    if mask.shape != shape:
        mask8 = (mask >> 8).astype(np.uint8)
        resized = Image.fromarray(mask8).resize(
            (shape[1], shape[0]), Image.Resampling.LANCZOS
        )
        mask = np.asarray(resized, dtype=np.uint16) * 257
    return mask.astype(np.float32)[:, :, None] / 65535.0


def _sequence_signature(paths, mask_path):
    digest = hashlib.sha256()
    for path in paths:
        resolved = Path(path).resolve()
        stat = resolved.stat()
        digest.update(str(resolved).encode())
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode())
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode())
        digest.update(b"\0")
    if mask_path:
        digest.update(str(Path(mask_path).resolve()).encode())
    return digest.hexdigest()


def _write_checkpoint(project, accumulated, next_index, frame_count, signature, config):
    image_path = _checkpoint_image_path(project)
    image_temporary = image_path.with_name(f".{image_path.name}.partial")
    tifffile.imwrite(
        str(image_temporary),
        accumulated,
        compression=config["tiff"]["compression"],
    )
    os.replace(image_temporary, image_path)
    metadata = {
        "next_index": next_index,
        "frame_count": frame_count,
        "width": accumulated.shape[1],
        "height": accumulated.shape[0],
        "sequence_signature": signature,
    }
    meta_path = _checkpoint_meta_path(project)
    meta_temporary = meta_path.with_name(f".{meta_path.name}.partial")
    meta_temporary.write_text(json.dumps(metadata, indent=2))
    os.replace(meta_temporary, meta_path)


def _resolve_inputs(project, selection, config):
    paths = []
    raw_exts = set(config["extensions"]["raw"])
    for rec in selection:
        if rec["decision"] != "keep":
            continue
        source = Path(rec["path"])
        if source.suffix.lower() in raw_exts:
            developed = developed_path(project, rec)
            if not developed.exists():
                raise RuntimeError(
                    f"Missing developed TIFF for selected RAW: {source.name}"
                )
            paths.append(developed)
        else:
            paths.append(source)
    return paths


def cmd_stack(args, log):
    config = read_config(args.project)
    selection = read_manifest(args.project, "selection")
    if not selection:
        log.warning("No selection found. Run 'select' first.")
        return

    keep_paths = _resolve_inputs(args.project, selection, config)
    if not keep_paths:
        log.warning("No frames to stack.")
        return

    output = _stack_path(args.project)
    force = getattr(args, "force", False)
    resume = getattr(args, "resume", False)
    meta_path = _checkpoint_meta_path(args.project)
    image_path = _checkpoint_image_path(args.project)
    if output.exists() and resume and not (meta_path.exists() and image_path.exists()):
        log.info(f"Completed stack already exists: {output}")
        return
    if output.exists() and not (force or resume):
        raise RuntimeError(
            f"Output already exists: {output}. Pass --force to overwrite it."
        )

    first_arr = _load_frame(keep_paths[0])
    height, width = first_arr.shape[:2]
    mask = _load_mask(args.mask, (height, width)) if args.mask else None
    signature = _sequence_signature(keep_paths, args.mask)

    stack_dir = args.project / "stacks"
    stack_dir.mkdir(parents=True, exist_ok=True)
    start_index = 1
    accumulated = first_arr.copy()
    frame_count = 1

    if resume and meta_path.exists() and image_path.exists():
        metadata = json.loads(meta_path.read_text())
        if metadata.get("sequence_signature") != signature:
            raise RuntimeError("Checkpoint does not match the current frame sequence or mask")
        accumulated = _load_frame(image_path)
        if accumulated.shape != first_arr.shape:
            raise RuntimeError("Checkpoint dimensions do not match the input frames")
        frame_count = int(metadata["frame_count"])
        start_index = int(metadata["next_index"])
        log.info(
            f"Resumed from checkpoint: {frame_count} frames, next index {start_index}"
        )

    interval = max(1, int(config["checkpoint"]["interval_frames"]))
    log.info(
        f"Stacking {len(keep_paths)} frames, {width}x{height}, "
        f"checkpoint every {interval} frames"
    )

    for idx in range(start_index, len(keep_paths)):
        path = keep_paths[idx]
        arr = _load_frame(path)
        if arr.shape != first_arr.shape:
            raise RuntimeError(
                f"Dimension/channel mismatch: {path.name} has {arr.shape}, "
                f"expected {first_arr.shape}"
            )

        maximum = np.maximum(accumulated, arr)
        if mask is None:
            accumulated = maximum
        else:
            accumulated = np.rint(
                accumulated.astype(np.float32) * (1.0 - mask)
                + maximum.astype(np.float32) * mask
            ).astype(np.uint16)
        frame_count += 1

        if frame_count % interval == 0:
            _write_checkpoint(
                args.project,
                accumulated,
                idx + 1,
                frame_count,
                signature,
                config,
            )
            log.info(f"Checkpoint: {frame_count} frames stacked")

    output_temporary = output.with_name(f".{output.name}.partial")
    tifffile.imwrite(
        str(output_temporary),
        accumulated,
        compression=config["tiff"]["compression"],
    )
    os.replace(output_temporary, output)
    preview = _preview_path(args.project)
    preview_temporary = preview.with_name(f".{preview.name}.partial")
    Image.fromarray((accumulated >> 8).astype(np.uint8), "RGB").save(
        str(preview_temporary), "JPEG", quality=90
    )
    os.replace(preview_temporary, preview)

    meta_path.unlink(missing_ok=True)
    image_path.unlink(missing_ok=True)
    write_manifest(
        args.project,
        "stack",
        [
            {
                "frames": frame_count,
                "width": width,
                "height": height,
                "stack_path": str(output),
                "preview_path": str(_preview_path(args.project)),
            }
        ],
    )
    log.info(f"Stack complete: {frame_count} frames -> {output}")
