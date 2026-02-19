"""Machine settings persistence via INI file.

Reads and writes ``MachineSettings`` to ``inkburn.ini`` located alongside
the extension scripts.
"""

import configparser
import logging
import os
from typing import Optional

from models.machine import DebugLevel, MachineSettings

logger = logging.getLogger(__name__)

_CONFIG_SECTION = "InkBurn"

_INI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "inkburn.ini",
)


def _config_path() -> str:
    """Return the absolute path to the INI file."""
    return _INI_PATH


def load_machine_settings(path: Optional[str] = None) -> MachineSettings:
    """Load machine settings from the INI file.

    Missing keys receive their dataclass defaults.

    Args:
        path: Optional override for the INI file path (useful for tests).

    Returns:
        Populated MachineSettings instance.
    """
    path = path or _config_path()
    cp = configparser.ConfigParser()
    if os.path.exists(path):
        cp.read(path, encoding="utf-8")

    if not cp.has_section(_CONFIG_SECTION):
        return MachineSettings()

    cfg = cp[_CONFIG_SECTION]
    return MachineSettings(
        max_power=cfg.getint("max_power", fallback=1000),
        max_speed=cfg.getint("max_speed", fallback=6000),
        travel_speed=cfg.getint("travel_speed", fallback=4000),
        resolution=cfg.getfloat("resolution", fallback=0.1),
        kerf_width=cfg.getfloat("kerf_width", fallback=0.0),
        laser_mode=cfg.getboolean("laser_mode", fallback=True),
        debug_level=DebugLevel(cfg.get("debug_level", fallback="off")),
        path_optimization=cfg.getboolean("path_optimization", fallback=True),
        direction_optimization=cfg.getboolean("direction_optimization", fallback=True),
        autolaunch=cfg.getboolean("autolaunch", fallback=False),
    )


def save_machine_settings(
    settings: MachineSettings, path: Optional[str] = None
) -> None:
    """Save machine settings to the INI file.

    Args:
        settings: Settings to persist.
        path: Optional override for the INI file path.
    """
    path = path or _config_path()
    cp = configparser.ConfigParser()
    cp[_CONFIG_SECTION] = {
        "max_power": str(settings.max_power),
        "max_speed": str(settings.max_speed),
        "travel_speed": str(settings.travel_speed),
        "resolution": str(settings.resolution),
        "kerf_width": str(settings.kerf_width),
        "laser_mode": str(settings.laser_mode).lower(),
        "debug_level": settings.debug_level.value,
        "path_optimization": str(settings.path_optimization).lower(),
        "direction_optimization": str(settings.direction_optimization).lower(),
        "autolaunch": str(settings.autolaunch).lower(),
    }
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
        
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)
    logger.debug("Machine settings saved to %s", path)
