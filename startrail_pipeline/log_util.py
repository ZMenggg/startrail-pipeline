import logging
import sys


def setup_logging(project_path=None, verbosity=0):
    level = logging.INFO
    if verbosity >= 2:
        level = logging.DEBUG

    logger = logging.getLogger("startrail")
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        fmt = logging.Formatter("%(levelname)s %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    if project_path:
        log_dir = project_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)

    return logger
