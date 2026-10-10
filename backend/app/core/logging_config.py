"""
Basic logging setup for AgentForge.

Kept deliberately simple for Phase 1: one function that configures Python's
built-in `logging` module so every log line shows the time, the logger name
(which file/module logged it), the level, and the message. That's enough to
answer "what happened, where, and when" while we build.

Later phases (Observability, section 19 of the spec) will add structured
JSON logging and event tracing for agent/tool activity. This module is the
foundation that gets extended, not replaced.
"""

import logging

from app.core.config import settings

_CONFIGURED = False


def setup_logging() -> None:
    """
    Configure the root logger once. Safe to call multiple times —
    only the first call actually does anything.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a given module, e.g. get_logger(__name__).
    Ensures logging is configured before handing back the logger.
    """
    setup_logging()
    return logging.getLogger(name)
