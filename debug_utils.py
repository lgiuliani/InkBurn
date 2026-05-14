#!debug_utils.py
"""Debug output helpers for Inkscape extensions."""

import inkex

from models.machine import DebugLevel, MachineSettings

# Ordered from least to most verbose — used for threshold comparison.
_LEVEL_ORDER = [DebugLevel.CRITICAL, DebugLevel.WARNING, DebugLevel.INFO]


def debug_output(
    settings: MachineSettings,
    message: str,
    level: DebugLevel = DebugLevel.WARNING,
) -> None:
    """Write a debug message if the configured verbosity allows it.

    Args:
        settings: Machine settings supplying the active debug level.
        message: Text to emit.
        level: Verbosity level of this message.
    """
    if _LEVEL_ORDER.index(settings.debug_level) >= _LEVEL_ORDER.index(level):
        inkex.utils.debug(message)