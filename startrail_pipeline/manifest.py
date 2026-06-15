import csv
import json
import os
from pathlib import Path


def read_manifest(project_path, kind="inventory"):
    path = project_path / "manifests" / f"{kind}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def write_manifest(project_path, kind, records):
    manifest_dir = project_path / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    json_path = manifest_dir / f"{kind}.json"
    json_temporary = manifest_dir / f".{kind}.json.partial"
    with open(json_temporary, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(json_temporary, json_path)

    csv_path = manifest_dir / f"{kind}.csv"
    csv_temporary = manifest_dir / f".{kind}.csv.partial"
    with open(csv_temporary, "w", newline="") as f:
        if records:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
        f.flush()
        os.fsync(f.fileno())
    os.replace(csv_temporary, csv_path)
