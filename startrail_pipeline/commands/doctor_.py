import shutil
import subprocess
import sys
from pathlib import Path

from startrail_pipeline.config import read_config
from startrail_pipeline.raw_backend import find_darktable, probe_darktable

def _check_python():
    v = sys.version_info
    ok = v >= (3, 11)
    return ok, f"Python {v.major}.{v.minor}.{v.micro} ({'OK' if ok else 'need 3.11+'})"


def _check_dep(name, import_name=None):
    try:
        __import__(import_name or name)
        return True, f"{name} found"
    except ImportError:
        return False, f"{name} NOT found"


def _check_exiftool():
    p = shutil.which("exiftool")
    if p:
        try:
            r = subprocess.run([p, "-ver"], capture_output=True, text=True, timeout=5)
            return True, f"exiftool {r.stdout.strip()}"
        except Exception:
            return True, "exiftool found (version unknown)"
    return False, "exiftool NOT found (optional)"


def _check_darktable(config=None):
    p = find_darktable(config)
    if p:
        ok, detail = probe_darktable(p)
        if ok:
            return True, f"{detail} ({p})"
        return False, f"darktable-cli unusable: {detail} ({p})"
    return False, "darktable-cli NOT found (optional)"


def _check_rawpy():
    try:
        import rawpy
        return True, f"rawpy {rawpy.__version__}"
    except ImportError:
        return False, "rawpy NOT found (optional, needed if no darktable-cli)"


def _check_disk(project_path):
    if project_path and project_path.exists():
        try:
            usage = shutil.disk_usage(project_path)
            free_gb = usage.free / (1024**3)
            return True, f"{free_gb:.1f} GB free"
        except OSError:
            return False, "Cannot determine"
    return None, "No project path"


def cmd_doctor(args, log):
    project = getattr(args, "project", None)
    config = read_config(project) if project else None
    checks = [
        ("Python", _check_python()),
        ("numpy", _check_dep("numpy")),
        ("Pillow", _check_dep("Pillow", import_name="PIL")),
        ("tifffile", _check_dep("tifffile")),
        ("exiftool", _check_exiftool()),
        ("darktable-cli", _check_darktable(config)),
        ("rawpy", _check_rawpy()),
    ]

    if project:
        disk_ok, disk_msg = _check_disk(project)
        checks.append(("Disk space", (disk_ok, disk_msg)))

    all_ok = True
    required = {"Python", "numpy", "Pillow", "tifffile"}
    for name, (ok, msg) in checks:
        status = "OK" if ok else "MISSING"
        log.info(f"{status:8s} {name}: {msg}")
        if name in required and not ok:
            all_ok = False

    log.info(f"All required checks passed: {all_ok}")
    raw_ok = dict(checks)["darktable-cli"][0] or dict(checks)["rawpy"][0]
    log.info(f"RAW processing available: {raw_ok}")
    if getattr(args, "require_raw", False) and not raw_ok:
        raise RuntimeError(
            "RAW processing was required, but neither a working darktable-cli "
            "nor rawpy is available."
        )
    return all_ok
