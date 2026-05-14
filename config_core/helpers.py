"""GTK helper widgets and parameter schema for job configuration."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from typing import Dict, List, Tuple

from models.job import JobParamSchemaRow, JobType, job_param_schema_rows

ParamDef = JobParamSchemaRow

PARAM_SCHEMA: Dict[JobType, List[ParamDef]] = job_param_schema_rows()


def make_labeled_spin(
    label_text: str, min_val: float, max_val: float, step: float
) -> Tuple[Gtk.Box, Gtk.SpinButton]:
    """Create a horizontal box with a label and a spin button.

    Args:
        label_text: Label to display.
        min_val: Minimum spin value.
        max_val: Maximum spin value.
        step: Step increment.

    Returns:
        Tuple of (container box, spin button widget).
    """
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    lbl = Gtk.Label(label=label_text, xalign=0)
    lbl.set_width_chars(22)
    spin = Gtk.SpinButton.new_with_range(min_val, max_val, step)
    box.pack_start(lbl, False, False, 0)
    box.pack_start(spin, True, True, 0)
    return box, spin


def make_labeled_check(label_text: str) -> Tuple[Gtk.Box, Gtk.CheckButton]:
    """Create a horizontal box with a check button.

    Args:
        label_text: Label to display.

    Returns:
        Tuple of (container box, check button widget).
    """
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    chk = Gtk.CheckButton(label=label_text)
    box.pack_start(chk, True, True, 0)
    return box, chk


def make_labeled_combo(
    label_text: str, options: List[Tuple[str, str]]
) -> Tuple[Gtk.Box, Gtk.ComboBoxText]:
    """Create a horizontal box with a label and combo box.

    Args:
        label_text: Label to display.
        options: List of (id, display_text) tuples.

    Returns:
        Tuple of (container box, combo box widget).
    """
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    lbl = Gtk.Label(label=label_text, xalign=0)
    lbl.set_width_chars(22)
    combo = Gtk.ComboBoxText()
    for opt_id, opt_label in options:
        combo.append(opt_id, opt_label)
    box.pack_start(lbl, False, False, 0)
    box.pack_start(combo, True, True, 0)
    return box, combo
