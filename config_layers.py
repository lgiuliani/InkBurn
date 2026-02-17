"""Inkscape extension entry point — Layer & Job Configuration.

Opens a GTK 3.24 dialog where users can manage multiple laser jobs
per SVG layer: add/remove/reorder jobs, toggle active state, and
edit per-job parameters.
"""

import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import inkex
from lxml import etree

from config_core.svg_io import load_layers, save_layers
from config_core.ui import UIManager


class LayerConfigDialog(inkex.EffectExtension):
    """Inkscape effect extension opening the layer/job editor."""

    def effect(self) -> None:
        """Run the effect: load layers, show dialog, save back."""
        svg_root = self.document.getroot()

        layers, elements = load_layers(svg_root)
        if not layers:
            inkex.errormsg("No layers found in document.")
            return

        manager = UIManager(layers, elements)

        manager.window.show_all()
        manager.window.connect("destroy", Gtk.main_quit)
        Gtk.main()

        if manager.saved:
            count = save_layers(layers, elements)
            if count > 0:
                etree.ElementTree(self.document.getroot()).write(
                    self.options.output,
                    xml_declaration=True,
                    encoding="utf-8",
                    pretty_print=True,
                )


if __name__ == "__main__":
    LayerConfigDialog().run()
