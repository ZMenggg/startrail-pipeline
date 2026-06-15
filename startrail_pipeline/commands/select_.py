import csv
from pathlib import Path

from startrail_pipeline.manifest import read_manifest, write_manifest

VALID_DECISIONS = {"keep", "review", "reject_candidate"}


def _read_overrides(override_path):
    overrides = {}
    with open(override_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row.get("relative_path") or row.get("path", "")
            decision = row.get("decision", "review")
            if decision not in VALID_DECISIONS:
                raise ValueError(
                    f"Invalid decision '{decision}' for {key}; expected one of "
                    f"{', '.join(sorted(VALID_DECISIONS))}"
                )
            overrides[key] = decision
    return overrides


def cmd_select(args, log):
    inventory = read_manifest(args.project, "inventory")
    if not inventory:
        log.warning("No inventory found.")
        return

    analysis = read_manifest(args.project, "analysis")
    analysis_map = {}
    for a in analysis:
        key = a.get("relative_path") or Path(a["path"]).name
        analysis_map[key] = a

    overrides = {}
    if args.override:
        overrides = _read_overrides(args.override)
        log.info(f"Loaded {len(overrides)} overrides from {args.override}")

    selections = []
    for rec in inventory:
        key = rec.get("relative_path") or Path(rec["path"]).name
        if key in overrides:
            decision = overrides[key]
        else:
            a = analysis_map.get(key, {})
            anomalies = a.get("anomalies", [])
            if any("_high" in an for an in anomalies):
                decision = "review"
            elif anomalies:
                decision = "review"
            else:
                decision = "keep"
        selections.append(
            {
                "path": rec["path"],
                "relative_path": rec.get("relative_path", ""),
                "decision": decision,
                "override": key in overrides,
            }
        )

    write_manifest(args.project, "selection", selections)
    keeps = sum(1 for s in selections if s["decision"] == "keep")
    reviews = sum(1 for s in selections if s["decision"] == "review")
    rejects = sum(1 for s in selections if s["decision"] == "reject_candidate")
    log.info(f"Selection: {keeps} keep, {reviews} review, {rejects} reject_candidate")
