"""Standard library logging configuration."""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once for the application."""
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. re-imported in tests) — avoid duplicate handlers.
        root.setLevel(level)
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)
