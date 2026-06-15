import tomllib
from pathlib import Path

DEFAULT_CONFIG = {
    "extensions": {
        "raw": [".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf"],
        "image": [".tif", ".tiff", ".png", ".jpg", ".jpeg"],
    },
    "grouping": {"time_threshold_seconds": 120},
    "analysis": {
        "proxy_size": 1024,
        "mad_multiplier_low": 3.0,
        "mad_multiplier_high": 5.0,
    },
    "tiff": {"compression": "zlib"},
    "checkpoint": {"interval_frames": 50},
    "raw_developer": {
        "backend": "auto",
        "executable": "",
        "style_name": "",
        "estimated_tiff_size_ratio": 6.5,
        "disk_reserve_gb": 10,
    },
}


def read_config(project_path):
    path = project_path / "project.toml"
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    with open(path, "rb") as f:
        user_config = tomllib.load(f)
    merged = {}
    for key, value in DEFAULT_CONFIG.items():
        if isinstance(value, dict):
            merged[key] = {**value, **user_config.get(key, {})}
        else:
            merged[key] = user_config.get(key, value)
    return merged


def _toml_dumps(cfg, indent=0):
    lines = []
    for key, value in cfg.items():
        prefix = "  " * indent
        if isinstance(value, dict):
            lines.append(f"{prefix}[{key}]")
            lines.append(_toml_dumps(value, indent + 1))
        elif isinstance(value, list):
            items = ", ".join(repr(v) for v in value)
            lines.append(f"{prefix}{key} = [{items}]")
        elif isinstance(value, str):
            lines.append(f'{prefix}{key} = "{value}"')
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key} = {'true' if value else 'false'}")
        else:
            lines.append(f"{prefix}{key} = {value}")
    return "\n".join(lines)


def write_default_config(project_path, force=False):
    path = project_path / "project.toml"
    if path.exists() and not force:
        return
    with open(path, "w") as f:
        f.write(_toml_dumps(DEFAULT_CONFIG))
        f.write("\n")
