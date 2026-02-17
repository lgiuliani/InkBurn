"""Machine settings model for InkBurn extension.

Machine settings are persisted in an INI file and act as defaults and
upper bounds for per-job values.
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DebugLevel(str, Enum):
    """Verbosity level for extension debug output."""

    OFF = "off"
    MIN = "min"
    VERBOSE = "verbose"


@dataclass
class MachineSettings:
    """Machine-level configuration.

    These values are stored outside the SVG (in Inkscape preferences or
    INI file) and act as defaults / maxima for job parameters.

    Attributes:
        max_power: Maximum S value the controller supports.
        max_speed: Maximum feed rate in mm/min.
        travel_speed: Rapid travel speed in mm/min.
        resolution: Minimum positioning resolution in mm.
        kerf_width: Laser kerf width in mm (for offset compensation).
        laser_mode: Whether $32=1 laser mode is enabled.
        debug_level: Logging verbosity.
        path_optimization: Enable nearest-neighbor path reordering.
        direction_optimization: Enable path direction reversal.
        autolaunch: Auto-open generated file after export.
    """

    max_power: int = 1000
    max_speed: int = 6000
    travel_speed: int = 4000
    resolution: float = 0.1
    kerf_width: float = 0.0
    laser_mode: bool = True
    debug_level: DebugLevel = DebugLevel.OFF
    path_optimization: bool = True
    direction_optimization: bool = True
    autolaunch: bool = False

    def clamp_power(self, value: float) -> int:
        """Clamp a power value to [0, max_power].

        Args:
            value: Raw power value.

        Returns:
            Clamped integer power value.
        """
        clamped = int(max(0, min(value, self.max_power)))
        if clamped != int(value):
            logger.warning(
                "Power value %.0f clamped to %d (max_power=%d)",
                value, clamped, self.max_power,
            )
        return clamped

    def clamp_speed(self, value: float) -> int:
        """Clamp a speed value to [1, max_speed].

        Args:
            value: Raw speed value in mm/min.

        Returns:
            Clamped integer speed value.
        """
        clamped = int(max(1, min(value, self.max_speed)))
        if clamped != int(value):
            logger.warning(
                "Speed value %.0f clamped to %d (max_speed=%d)",
                value, clamped, self.max_speed,
            )
        return clamped
