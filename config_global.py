"""Inkscape extension entry point — General Machine Settings.

Opens a GTK 3.24 dialog for editing machine-level parameters that
are persisted in ``inkburn.ini`` and act as defaults / upper bounds
for per-job values.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import inkex

from models.machine import DebugLevel, MachineSettings
from persistence.preferences import load_machine_settings, save_machine_settings


class GlobalOptionsDialog(inkex.EffectExtension):
    """Inkscape effect extension for machine settings."""

    def effect(self) -> None:
        """Run the effect: load settings, show dialog, save on confirm."""
        settings = load_machine_settings()

        window = Gtk.Window(title="Ink/Burn : Machine Settings")
        window.connect("delete-event", Gtk.main_quit)
        window.set_default_size(600, 420)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12)
        grid = Gtk.Grid(row_spacing=6, column_spacing=12, margin=6)
        vbox.pack_start(grid, True, True, 0)

        row = 0

        # Max power
        grid.attach(Gtk.Label(label="Max laser power (S max)", xalign=0), 0, row, 1, 1)
        spin_max_power = Gtk.SpinButton.new_with_range(1, 65535, 100)
        spin_max_power.set_value(settings.max_power)
        grid.attach(spin_max_power, 1, row, 1, 1)
        row += 1

        # Max speed
        grid.attach(Gtk.Label(label="Max feed rate (mm/min)", xalign=0), 0, row, 1, 1)
        spin_max_speed = Gtk.SpinButton.new_with_range(1, 50000, 100)
        spin_max_speed.set_value(settings.max_speed)
        grid.attach(spin_max_speed, 1, row, 1, 1)
        row += 1

        # Travel speed
        grid.attach(Gtk.Label(label="Travel speed (mm/min)", xalign=0), 0, row, 1, 1)
        spin_travel_speed = Gtk.SpinButton.new_with_range(100, 50000, 100)
        spin_travel_speed.set_value(settings.travel_speed)
        grid.attach(spin_travel_speed, 1, row, 1, 1)
        row += 1

        # Resolution
        grid.attach(Gtk.Label(label="Resolution (mm)", xalign=0), 0, row, 1, 1)
        spin_resolution = Gtk.SpinButton.new_with_range(0.001, 1.0, 0.01)
        spin_resolution.set_digits(3)
        spin_resolution.set_value(settings.resolution)
        grid.attach(spin_resolution, 1, row, 1, 1)
        row += 1

        # Kerf width
        grid.attach(Gtk.Label(label="Kerf width (mm)", xalign=0), 0, row, 1, 1)
        spin_kerf = Gtk.SpinButton.new_with_range(0.0, 5.0, 0.01)
        spin_kerf.set_digits(2)
        spin_kerf.set_value(settings.kerf_width)
        grid.attach(spin_kerf, 1, row, 1, 1)
        row += 1

        # Laser mode ($32=1)
        chk_laser_mode = Gtk.CheckButton(label="Laser mode ($32=1)")
        chk_laser_mode.set_active(settings.laser_mode)
        grid.attach(chk_laser_mode, 0, row, 2, 1)
        row += 1

        # Path optimization
        chk_path_opt = Gtk.CheckButton(label="Enable path order optimization")
        chk_path_opt.set_active(settings.path_optimization)
        grid.attach(chk_path_opt, 0, row, 2, 1)
        row += 1

        # Direction optimization
        chk_dir_opt = Gtk.CheckButton(label="Enable path direction optimization")
        chk_dir_opt.set_active(settings.direction_optimization)
        grid.attach(chk_dir_opt, 0, row, 2, 1)
        row += 1

        # Autolaunch
        chk_autolaunch = Gtk.CheckButton(label="Auto-open file after export")
        chk_autolaunch.set_active(settings.autolaunch)
        grid.attach(chk_autolaunch, 0, row, 2, 1)
        row += 1

        # Debug level
        grid.attach(Gtk.Label(label="Debug level", xalign=0), 0, row, 1, 1)
        combo_debug = Gtk.ComboBoxText()
        for level in DebugLevel:
            combo_debug.append(level.value, level.value.capitalize())
        combo_debug.set_active_id(settings.debug_level.value)
        grid.attach(combo_debug, 1, row, 1, 1)
        row += 1

        # Buttons
        btns = Gtk.ButtonBox(spacing=10)
        btn_save = Gtk.Button(label="Save")
        btn_reset = Gtk.Button(label="Reset Defaults")
        btn_cancel = Gtk.Button(label="Cancel")
        btns.pack_start(btn_save, False, False, 0)
        btns.pack_start(btn_reset, False, False, 0)
        btns.pack_start(btn_cancel, False, False, 0)
        vbox.pack_start(btns, False, False, 0)

        def on_save(_: object) -> None:
            new_settings = MachineSettings(
                max_power=int(spin_max_power.get_value()),
                max_speed=int(spin_max_speed.get_value()),
                travel_speed=int(spin_travel_speed.get_value()),
                resolution=spin_resolution.get_value(),
                kerf_width=spin_kerf.get_value(),
                laser_mode=chk_laser_mode.get_active(),
                debug_level=DebugLevel(combo_debug.get_active_id() or "off"),
                path_optimization=chk_path_opt.get_active(),
                direction_optimization=chk_dir_opt.get_active(),
                autolaunch=chk_autolaunch.get_active(),
            )
            save_machine_settings(new_settings)
            Gtk.main_quit()

        def on_reset(_: object) -> None:
            defaults = MachineSettings()
            spin_max_power.set_value(defaults.max_power)
            spin_max_speed.set_value(defaults.max_speed)
            spin_travel_speed.set_value(defaults.travel_speed)
            spin_resolution.set_value(defaults.resolution)
            spin_kerf.set_value(defaults.kerf_width)
            chk_laser_mode.set_active(defaults.laser_mode)
            chk_path_opt.set_active(defaults.path_optimization)
            chk_dir_opt.set_active(defaults.direction_optimization)
            chk_autolaunch.set_active(defaults.autolaunch)
            combo_debug.set_active_id(defaults.debug_level.value)

        btn_save.connect("clicked", on_save)
        btn_cancel.connect("clicked", lambda _: Gtk.main_quit())
        btn_reset.connect("clicked", on_reset)

        window.add(vbox)
        window.show_all()
        Gtk.main()


if __name__ == "__main__":
    GlobalOptionsDialog().run()
