"""Logging configuration for the bot."""

import logging
import os


def configure_logging() -> None:
    """Configure root logging from the LOG_LEVEL environment variable."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)

    if not isinstance(level, int):
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    )
