#!/usr/bin/env python3
 #
 # This file is part of the InkBurn distribution (https://github.com/lgiuliani/InkBurn).
 # Copyright (c) 2025 LLaurent Giuliani.
 #
 # This program is free software: you can redistribute it and/or modify
 # it under the terms of the GNU General Public License as published by
 # the Free Software Foundation, version 3.
 #
 # This program is distributed in the hope that it will be useful, but
 # WITHOUT ANY WARRANTY; without even the implied warranty of
 # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 # General Public License for more details.
 #
 # You should have received a copy of the GNU General Public License
 # along with this program. If not, see <http://www.gnu.org/licenses/>.
 #
import os
import configparser
import inkex
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

CONFIG_SECTION = 'InkBurn'
DEFAULTS = {
    'autolaunch': 'false',
    'laser_program': 'LaserGRBL',
    'laser_path': '',
    'unit': 'mm',
    'max_travel_speed': '4000'
}


def get_config_path() -> str:
    path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(path, 'inkburn.ini')


def load_config() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    path = get_config_path()
    if os.path.exists(path):
        try:
            cp.read(path)
        except Exception:
            pass

    if not cp.has_section(CONFIG_SECTION):
        cp[CONFIG_SECTION] = DEFAULTS.copy()
    else:
        for k, v in DEFAULTS.items():
            if k not in cp[CONFIG_SECTION]:
                cp[CONFIG_SECTION][k] = v
    return cp


def save_config(cp: configparser.ConfigParser) -> None:
    path = get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        cp.write(f)


class GlobalOptionsDialog(inkex.EffectExtension):
    def effect(self):
        cp = load_config()
        cfg = cp[CONFIG_SECTION]

        window = Gtk.Window(title="Ink/Burn : Global options")
        window.connect("delete-event", Gtk.main_quit)
        window.set_default_size(600, 240)

        vbox = Gtk.VBox(spacing=6, margin=12)
        grid = Gtk.Grid(row_spacing=6, column_spacing=8, margin=6)
        vbox.pack_start(grid, True, True, 0)

        # Autolaunch
        chk_autolaunch = Gtk.CheckButton(label="Autolaunch laser program on export")
        chk_autolaunch.set_active(cfg.get('autolaunch', 'false').lower() == 'true')
        grid.attach(chk_autolaunch, 0, 0, 3, 1)

        # Laser program choice
        lbl_prog = Gtk.Label(label="Laser program", xalign=0)
        combo_prog = Gtk.ComboBoxText()
        combo_prog.append_text("LaserGRBL")
        combo_prog.append_text("Other")
        prog = cfg.get('laser_program', DEFAULTS['laser_program'])
        combo_prog.set_active(0 if prog == 'LaserGRBL' else 1)
        grid.attach(lbl_prog, 0, 1, 1, 1)
        grid.attach(combo_prog, 1, 1, 2, 1)

        # Program path and browse
        lbl_path = Gtk.Label(label="Program path", xalign=0)
        entry_path = Gtk.Entry()
        entry_path.set_text(cfg.get('laser_path', ''))
        btn_browse = Gtk.Button(label="Browse")

        def on_browse(_):
            dlg = Gtk.FileChooserDialog(title="Choose program", action=Gtk.FileChooserAction.OPEN)
            dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK)
            if dlg.run() == Gtk.ResponseType.OK:
                entry_path.set_text(dlg.get_filename())
            dlg.destroy()

        btn_browse.connect('clicked', on_browse)
        grid.attach(lbl_path, 0, 2, 1, 1)
        grid.attach(entry_path, 1, 2, 1, 1)
        grid.attach(btn_browse, 2, 2, 1, 1)

        # Unit
        lbl_unit = Gtk.Label(label="Unit", xalign=0)
        combo_unit = Gtk.ComboBoxText()
        combo_unit.append_text("mm")
        combo_unit.append_text("in")
        unit = cfg.get('unit', DEFAULTS['unit'])
        combo_unit.set_active(0 if unit == 'mm' else 1)
        grid.attach(lbl_unit, 0, 3, 1, 1)
        grid.attach(combo_unit, 1, 3, 2, 1)

        # Max travel speed
        lbl_speed = Gtk.Label(label="Max travel speed (mm/min)", xalign=0)
        adj_speed = Gtk.Adjustment(value=float(cfg.get('max_travel_speed', DEFAULTS['max_travel_speed'])), lower=100.0, upper=20000.0, step_increment=100.0)
        spin_speed = Gtk.SpinButton(adjustment=adj_speed, digits=0)
        grid.attach(lbl_speed, 0, 4, 1, 1)
        grid.attach(spin_speed, 1, 4, 2, 1)

        # Buttons
        btns = Gtk.ButtonBox(spacing=10)
        btn_save = Gtk.Button(label="Save")
        btn_reset = Gtk.Button(label="Reset defaults")
        btn_cancel = Gtk.Button(label="Cancel")
        btns.pack_start(btn_save, False, False, 0)
        btns.pack_start(btn_reset, False, False, 0)
        btns.pack_start(btn_cancel, False, False, 0)
        vbox.pack_start(btns, False, False, 0)

        def on_save(_):
            cp[CONFIG_SECTION]['autolaunch'] = 'true' if chk_autolaunch.get_active() else 'false'
            cp[CONFIG_SECTION]['laser_program'] = combo_prog.get_active_text() or DEFAULTS['laser_program']
            cp[CONFIG_SECTION]['laser_path'] = entry_path.get_text()
            cp[CONFIG_SECTION]['unit'] = combo_unit.get_active_text() or DEFAULTS['unit']
            cp[CONFIG_SECTION]['max_travel_speed'] = str(int(spin_speed.get_value_as_int()))
            try:
                save_config(cp)
            except Exception as e:
                inkex.errormsg(f"Failed to save config: {e}")
            Gtk.main_quit()

        def on_reset(_):
            cp[CONFIG_SECTION] = DEFAULTS.copy()
            chk_autolaunch.set_active(False)
            combo_prog.set_active(0)
            entry_path.set_text('')
            combo_unit.set_active(0)
            spin_speed.set_value(float(DEFAULTS['max_travel_speed']))

        btn_save.connect('clicked', on_save)
        btn_cancel.connect('clicked', lambda _: Gtk.main_quit())
        btn_reset.connect('clicked', on_reset)

        window.add(vbox)
        window.show_all()
        Gtk.main()


if __name__ == '__main__':
    GlobalOptionsDialog().run()
