"""Debug output helpers for Inkscape extensions."""

import inkex

from models import DebugLevel, MachineSettings

DEBUG_PRIORITY = {
    DebugLevel.CRITICAL: 0,
    DebugLevel.WARNING: 1,
    DebugLevel.INFO: 2,
}


def debug_output(
    settings: MachineSettings,
    message: str,
    level: DebugLevel = DebugLevel.WARNING,
) -> None:
    """Write a debug message if the configured verbosity allows it."""
    if DEBUG_PRIORITY[settings.debug_level] >= DEBUG_PRIORITY[level]:
        inkex.utils.debug(message)
