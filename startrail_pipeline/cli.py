import argparse
import sys
from pathlib import Path

from startrail_pipeline import __version__
from startrail_pipeline.commands.init_ import cmd_init
from startrail_pipeline.commands.inventory_ import cmd_inventory
from startrail_pipeline.commands.analyze_ import cmd_analyze
from startrail_pipeline.commands.select_ import cmd_select
from startrail_pipeline.commands.stack_ import cmd_stack
from startrail_pipeline.commands.doctor_ import cmd_doctor
from startrail_pipeline.commands.run_ import cmd_run
from startrail_pipeline.commands.develop_ import cmd_develop
from startrail_pipeline.commands.preview_ import cmd_preview
from startrail_pipeline.commands.gap_fill_ import cmd_gap_fill


def build_parser():
    p = argparse.ArgumentParser(
        prog="startrail",
        description="Star trail batch processing pipeline",
    )
    p.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    p.add_argument(
        "-v", "--verbose", action="count", default=0, help="increase verbosity"
    )

    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="Create a new project")
    sp.add_argument("project", type=Path, help="Project directory path")
    sp.add_argument("--force", action="store_true", help="Overwrite existing config")

    sp = sub.add_parser("inventory", help="Inventory source files")
    sp.add_argument("project", type=Path, help="Project directory")
    sp.add_argument("--source", "-s", type=Path, required=True, help="Source directory")

    sp = sub.add_parser("analyze", help="Analyze frames for quality")
    sp.add_argument("project", type=Path, help="Project directory")

    sp = sub.add_parser("select", help="Generate selection manifest")
    sp.add_argument("project", type=Path, help="Project directory")
    sp.add_argument(
        "--override", "-o", type=Path, default=None, help="CSV with manual overrides"
    )

    sp = sub.add_parser("develop", help="Develop RAW frames")
    sp.add_argument("project", type=Path, help="Project directory")
    sp.add_argument("--style", default=None, help="darktable style name")
    sp.add_argument(
        "--raw-backend",
        choices=("auto", "darktable", "rawpy"),
        default="auto",
        help="RAW developer backend",
    )
    sp.add_argument("--force", action="store_true", help="Redevelop valid outputs")

    sp = sub.add_parser("stack", help="Stack selected frames")
    sp.add_argument("project", type=Path, help="Project directory")
    sp.add_argument("--mask", "-m", type=Path, default=None, help="Sky mask (grayscale)")
    sp.add_argument(
        "--resume", action="store_true", help="Resume from last checkpoint"
    )
    sp.add_argument("--force", action="store_true", help="Overwrite an existing stack")

    sp = sub.add_parser("preview", help="Generate preview images")
    sp.add_argument("project", type=Path, help="Project directory")

    sp = sub.add_parser("run", help="Run full pipeline from source")
    sp.add_argument("project", type=Path, help="Project directory")
    sp.add_argument("--source", "-s", type=Path, required=True, help="Source directory")
    sp.add_argument("--style", default=None, help="darktable style name")
    sp.add_argument(
        "--raw-backend",
        choices=("auto", "darktable", "rawpy"),
        default="auto",
        help="RAW developer backend",
    )
    sp.add_argument("--mask", type=Path, default=None, help="Sky mask")
    sp.add_argument(
        "--override",
        "-o",
        type=Path,
        default=None,
        help="CSV with manual frame decisions",
    )
    sp.add_argument(
        "--accept-review",
        action="store_true",
        help="Continue even when frames require manual review",
    )
    sp.add_argument(
        "--resume",
        action="store_true",
        help="Resume stacking from a compatible checkpoint",
    )
    sp.add_argument("--force", action="store_true", help="Overwrite existing outputs")

    sp = sub.add_parser("doctor", help="Check system requirements")
    sp.add_argument("--project", type=Path, default=None, help="Project directory")
    sp.add_argument(
        "--require-raw",
        action="store_true",
        help="Fail when no working RAW backend is available",
    )

    sp = sub.add_parser("gap-fill", help="Fill short regular star-trail gaps")
    sp.add_argument("input", type=Path, help="Input 16-bit RGB TIFF")
    sp.add_argument("output", type=Path, help="Output TIFF")
    sp.add_argument("--dx", type=int, default=1, help="Trail direction X step")
    sp.add_argument("--dy", type=int, default=3, help="Trail direction Y step")
    sp.add_argument(
        "--sky-fraction",
        type=float,
        default=0.9,
        help="Top fraction of image to process",
    )
    sp.add_argument("--force", action="store_true", help="Overwrite output")

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    from startrail_pipeline.log_util import setup_logging

    log = setup_logging(
        project_path=getattr(args, "project", None),
        verbosity=args.verbose,
    )

    commands = {
        "init": cmd_init,
        "inventory": cmd_inventory,
        "analyze": cmd_analyze,
        "select": cmd_select,
        "develop": cmd_develop,
        "stack": cmd_stack,
        "preview": cmd_preview,
        "run": cmd_run,
        "doctor": cmd_doctor,
        "gap-fill": cmd_gap_fill,
    }

    try:
        commands[args.command](args, log)
    except Exception as e:
        log.error(str(e))
        sys.exit(1)
