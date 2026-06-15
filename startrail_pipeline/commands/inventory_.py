import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from startrail_pipeline.config import read_config
from startrail_pipeline.manifest import read_manifest, write_manifest


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _exif_data(path):
    exiftool = shutil.which("exiftool")
    if not exiftool:
        return {}
    try:
        result = subprocess.run(
            [
                exiftool,
                "-json",
                "-DateTimeOriginal",
                "-Make",
                "-Model",
                "-ExposureTime",
                "-ISO",
                "-FNumber",
                "-FocalLength",
                "-ImageWidth",
                "-ImageHeight",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        if not data:
            return {}
        src = data[0]
        out = {}
        if "DateTimeOriginal" in src and src["DateTimeOriginal"]:
            try:
                dt = datetime.strptime(src["DateTimeOriginal"], "%Y:%m:%d %H:%M:%S")
                out["capture_time"] = dt.isoformat()
            except ValueError:
                pass
        for k in ("Make", "Model", "ExposureTime", "ISO", "FNumber", "FocalLength",
                  "ImageWidth", "ImageHeight"):
            if k in src:
                out[k] = src[k]
        return out
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}


def _collect_files(source_dir, raw_exts, image_exts):
    all_exts = set(raw_exts) | set(image_exts)
    files = []
    for p in sorted(source_dir.rglob("*")):
        if p.suffix.lower() in all_exts and p.is_file():
            files.append(p)
    return files


def cmd_inventory(args, log):
    source = args.source.resolve()
    if not source.is_dir():
        log.error(f"Source directory not found: {source}")
        raise SystemExit(1)

    config = read_config(args.project)
    raw_exts = config["extensions"]["raw"]
    image_exts = config["extensions"]["image"]
    files = _collect_files(source, raw_exts, image_exts)

    if not files:
        log.warning(f"No supported files found in {source}")
        write_manifest(args.project, "inventory", [])
        return

    previous = {
        record.get("path"): record
        for record in read_manifest(args.project, "inventory")
    }
    records = []
    reused = 0
    for p in files:
        stat = p.stat()
        mtime = datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat()
        old = previous.get(str(p))
        unchanged = (
            old
            and old.get("size") == stat.st_size
            and old.get("mtime") == mtime
            and old.get("sha256")
        )
        if unchanged:
            exif = old.get("exif", {})
            sha256 = old["sha256"]
            reused += 1
        else:
            exif = _exif_data(p)
            sha256 = _sha256(p)
            after = p.stat()
            if after.st_size != stat.st_size or after.st_mtime_ns != stat.st_mtime_ns:
                raise RuntimeError(f"Source file changed while inventorying: {p}")
        rec = {
            "path": str(p),
            "relative_path": str(p.relative_to(source)),
            "size": stat.st_size,
            "mtime": mtime,
            "extension": p.suffix.lower(),
            "sha256": sha256,
            "exif": exif,
        }
        records.append(rec)

    records.sort(
        key=lambda rec: (
            rec["exif"].get("capture_time") or rec["mtime"],
            rec["relative_path"],
        )
    )
    write_manifest(args.project, "inventory", records)
    log.info(f"Inventoried {len(records)} files; reused {reused} unchanged records")
