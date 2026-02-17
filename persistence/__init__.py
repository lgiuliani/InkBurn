"""Persistence layer for InkBurn extension."""

from persistence.svg_io import load_layers, save_layers, clean_stale_job_attrs
from persistence.preferences import load_machine_settings, save_machine_settings

__all__ = [
    "load_layers",
    "save_layers",
    "clean_stale_job_attrs",
    "load_machine_settings",
    "save_machine_settings",
]
