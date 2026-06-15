from pathlib import Path

from startrail_pipeline.config import read_config
from startrail_pipeline.commands.init_ import cmd_init
from startrail_pipeline.commands.inventory_ import cmd_inventory
from startrail_pipeline.commands.analyze_ import cmd_analyze
from startrail_pipeline.commands.select_ import cmd_select
from startrail_pipeline.commands.develop_ import cmd_develop
from startrail_pipeline.commands.stack_ import cmd_stack
from startrail_pipeline.commands.preview_ import cmd_preview
from startrail_pipeline.manifest import read_manifest, write_manifest


def ensure_analysis_available(analysis):
    unavailable = [
        r for r in analysis if "proxy_missing" in r.get("anomalies", [])
    ]
    if unavailable:
        raise RuntimeError(
            f"Cannot continue: {len(unavailable)} RAW frame(s) have no usable "
            "preview, so automatic quality analysis was not performed. Fix the "
            "RAW preview backend and run again."
        )


def cmd_run(args, log):
    log.info("=== Running full pipeline ===")

    args.force = getattr(args, "force", False)
    args.override = getattr(args, "override", None)
    if not hasattr(args, "style") or args.style is None:
        args.style = None
    if not hasattr(args, "mask") or args.mask is None:
        args.mask = None
    args.resume = getattr(args, "resume", False)

    cmd_init(args, log)
    cmd_inventory(args, log)
    cmd_preview(args, log)
    cmd_analyze(args, log)
    cmd_select(args, log)

    selection = read_manifest(args.project, "selection")
    analysis = read_manifest(args.project, "analysis")
    ensure_analysis_available(analysis)
    review_count = sum(r["decision"] == "review" for r in selection)
    accept_review = getattr(args, "accept_review", False)
    if review_count and not accept_review:
        log.warning(
            f"Stopped before stacking: {review_count} frame(s) require review. "
            "Edit an override CSV and run select again, or pass --accept-review."
        )
        return
    if review_count and accept_review:
        for record in selection:
            if record["decision"] == "review":
                record["decision"] = "keep"
                record["auto_accepted_review"] = True
        write_manifest(args.project, "selection", selection)
        log.info(f"Accepted {review_count} review frame(s) for this automatic stack")

    has_raw = any(
        Path(r["path"]).suffix.lower()
        in read_config(args.project)["extensions"]["raw"]
        for r in selection
        if r["decision"] == "keep"
    )
    if has_raw:
        cmd_develop(args, log)

    cmd_stack(args, log)

    log.info("=== Pipeline complete ===")
