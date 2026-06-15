from pathlib import Path

from PIL import Image, ImageOps

from startrail_pipeline.config import read_config
from startrail_pipeline.manifest import read_manifest
from startrail_pipeline.raw_backend import generate_raw_preview


def proxy_path(project, relative_path):
    rel = Path(relative_path)
    return project / "proxies" / rel.parent / f"{rel.name}.jpg"


def cmd_preview(args, log):
    inventory = read_manifest(args.project, "inventory")
    if not inventory:
        log.warning("No inventory found.")
        return

    preview_dir = args.project / "proxies"
    preview_dir.mkdir(parents=True, exist_ok=True)
    config = read_config(args.project)
    raw_extensions = set(config["extensions"]["raw"])
    max_size = int(config["analysis"]["proxy_size"])

    count = 0
    failures = 0
    for rec in inventory:
        src = Path(rec["path"])
        dst = proxy_path(args.project, rec.get("relative_path", Path(src).name))
        if dst.exists():
            continue
        if src.suffix.lower() in raw_extensions:
            if generate_raw_preview(src, dst, max_size, config, log):
                count += 1
            else:
                failures += 1
            continue
        try:
            img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            temporary = dst.with_name(f".{dst.name}.partial")
            img.save(temporary, "JPEG", quality=85)
            temporary.replace(dst)
            count += 1
        except Exception as e:
            log.warning(f"Cannot preview {src}: {e}")
            failures += 1

    log.info(
        f"Generated {count} previews in {preview_dir}"
        + (f"; {failures} failed" if failures else "")
    )
