from startrail_pipeline.config import write_default_config


DIRS = [
    "manifests",
    "proxies",
    "selected",
    "developed",
    "masks",
    "stacks",
    "composites",
    "exports",
    "reports",
    "logs",
]


def cmd_init(args, log):
    project = args.project
    if project.exists() and not args.force:
        log.info(f"Project directory exists: {project}")
    project.mkdir(parents=True, exist_ok=True)
    for d in DIRS:
        (project / d).mkdir(parents=True, exist_ok=True)
    write_default_config(project, force=args.force)
    log.info(f"Initialized project at {project}")
