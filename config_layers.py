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
import inkex
from lxml import etree
from common import list_layers, get_layer_name, layer_distance
from config_global import load_config, CONFIG_SECTION

# GTK3 for the GUI
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import Gdk

# Defaults constants
DEFAULT_MAX_TRAVEL_SPEED = 10000  # Maximum travel speed in mm/min
DEFAULT_DIST_UNIT = 'mm'        # Default distance unit

# GUI layout constants
ROW_HEIGHT = 30      # approx height per row in pixels
HEADER_HEIGHT = 150  # header height in pixels
MAX_HEIGHT = 800     # max dialog height
DEFAULT_WIDTH = 650  # dialog width

#Functions
def human_time(minutes: float) -> tuple[str, int]:
    """Convert minutes (float) to human-readable H:MM:SS string and total seconds."""
    total_seconds = int(minutes * 60)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:d}:{minutes:02d}:{seconds:02d}", total_seconds

class LayerDataDialog(inkex.EffectExtension):
    
    def effect(self):
        svg = self.document.getroot()
        # Load global configuration (inkburn.ini)
        cp = load_config()
        cfg = cp[CONFIG_SECTION]
        unit = cfg.get('unit', 'mm')
        travel_speed = float(cfg.get('max_travel_speed', '4000'))
        
        layers = list(list_layers(svg))
        if not layers:
            inkex.errormsg("No layers found.")
            return

        # Compute desired height to show all layers; cap to screen and MAX_HEIGHT
        desired_height = HEADER_HEIGHT + ROW_HEIGHT * (len(layers) + 1)
        screen = Gdk.Screen.get_default()
        # Prefer monitor geometry (avoids deprecated get_height()); fallback safely
        if screen is not None:
            try:
                geom = screen.get_monitor_geometry(0)
                screen_height = geom.height
            except Exception:
                # last resort fallback
                screen_height = getattr(screen, 'get_height', lambda: MAX_HEIGHT)()
        else:
            screen_height = MAX_HEIGHT
        # leave some margin from screen edges
        max_allowed = min(screen_height - 80, MAX_HEIGHT)
        height = min(desired_height, max_allowed)

        window = Gtk.Window(title="Ink/Burn : Configure layers")
        window.connect("delete-event", Gtk.main_quit)
        # Force width so both panes are visible; height is dynamic but fixed at creation
        window.set_default_size(DEFAULT_WIDTH, height)
        window.set_resizable(False)

        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=12)

        # Horizontal split: left = layer list, right = parameters for selected layer
        hbox = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        root_box.pack_start(hbox, True, True, 0)

        # Left: list of layers
        left_scrolled = Gtk.ScrolledWindow()
        left_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        # Ensure left pane can scroll vertically when there are many layers
        LEFT_PANE_WIDTH = 260
        left_scrolled.set_size_request(LEFT_PANE_WIDTH, -1)
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        left_scrolled.add(listbox)

        # Right: parameter editor for selected layer
        right_frame = Gtk.Frame(label="Layer parameters")
        right_box = Gtk.Grid(row_spacing=6, column_spacing=10, margin=8)
        # Fix right pane width so its controls are always visible
        RIGHT_PANE_WIDTH = DEFAULT_WIDTH - LEFT_PANE_WIDTH - 40
        if RIGHT_PANE_WIDTH < 200:
            RIGHT_PANE_WIDTH = 200
        right_frame.set_size_request(RIGHT_PANE_WIDTH, -1)
        right_frame.add(right_box)

        hbox.add1(left_scrolled)
        hbox.add2(right_frame)

        # Bottom: global summary and buttons
        summary_lbl = Gtk.Label(label="Total: 0:00:00", xalign=0)

        entries = []  # list of dicts per layer

        # Helper to compute and format a layer's total time (minutes)
        def compute_layer_minutes(entry):
            cp = int(entry['spin_p'].get_value_as_int())
            cs = int(entry['spin_s'].get_value_as_int())
            engr = entry['eng'] * cp
            trav = entry['trv'] * cp
            e_min = (engr / cs) if cs > 0 else 0
            t_min = (trav / travel_speed)
            return e_min + t_min, engr, trav

        def update_global_summary():
            total = 0.0
            for e in entries:
                if e['chk'].get_active():
                    mins, _, _ = compute_layer_minutes(e)
                    total += mins
            human, _ = human_time(total)
            summary_lbl.set_text(f"Total: {human}")

        def update_row_summary(entry):
            mins, engr, trav = compute_layer_minutes(entry)
            hstr, _ = human_time(mins)
            entry['summary_lbl'].set_text(hstr)
            entry['summary_lbl'].set_tooltip_text(f"Engrave: {engr:.1f}mm\nTravel: {trav:.1f}mm")

        # Build list rows and parameter editor widgets
        last_point = (0.0, 0.0)
        for idx, layer in enumerate(layers):
            name = get_layer_name(layer)
            p = int(layer.get('data-passes') or 1)
            s = int(layer.get('data-speed') or 0)
            pw = int(layer.get('data-power') or 0)
            act = layer.get('data-active') == 'true'
            eng, trv, last_point = layer_distance(layer, last_point)
            eng = svg.unit_to_viewport(eng, unit)
            trv = svg.unit_to_viewport(trv, unit)

            # Left row widgets
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin=6)
            chk = Gtk.CheckButton()
            chk.set_active(act)
            name_lbl = Gtk.Label(label=name, xalign=0)
            summary = Gtk.Label(xalign=0)
            row_box.pack_start(chk, False, False, 0)
            row_box.pack_start(name_lbl, True, True, 0)
            row_box.pack_start(summary, False, False, 0)
            row.add(row_box)
            listbox.add(row)

            # Right-side parameter widgets (one set per layer, we'll show the selected one)
            spin_p = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=p, lower=1, upper=20, step_increment=1, page_increment=5, page_size=0), digits=0)
            spin_s = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=s, lower=1, upper=travel_speed, step_increment=10, page_increment=10, page_size=0), digits=0)
            spin_pw = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=pw, lower=0, upper=100, step_increment=1, page_increment=10, page_size=0), digits=0)
            lbl_time = Gtk.Label(xalign=0)

            entry = {
                'layer': layer,
                'eng': eng,
                'trv': trv,
                'spin_p': spin_p,
                'spin_s': spin_s,
                'spin_pw': spin_pw,
                'chk': chk,
                'row': row,
                'summary_lbl': summary,
                'lbl_time': lbl_time,
            }
            entries.append(entry)

            # Connect changes to update summaries/global summary
            def make_handlers(ent):
                def on_change(*_):
                    update_row_summary(ent)
                    update_global_summary()
                def on_active(tbtn, ent=ent):
                    # nothing to do on toggle except update summaries and possibly selection sensitivity
                    update_row_summary(ent)
                    update_global_summary()
                return on_change, on_active

            chg, tog = make_handlers(entry)
            spin_p.connect('value-changed', chg)
            spin_s.connect('value-changed', chg)
            spin_pw.connect('value-changed', chg)
            chk.connect('toggled', tog)

            # initialize summaries
            update_row_summary(entry)

        # Parameter editor contents (static controls, values will be set when row selected)
        lbl_pass = Gtk.Label(label="Passes:", xalign=0)
        lbl_speed = Gtk.Label(label="Speed (mm/min):", xalign=0)
        lbl_power = Gtk.Label(label="Power (%):", xalign=0)
        lbl_time_lab = Gtk.Label(label="Estimated time:", xalign=0)

        editor_pass = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=1, lower=1, upper=20, step_increment=1), digits=0)
        editor_speed = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=100, lower=1, upper=travel_speed, step_increment=10), digits=0)
        editor_power = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=0, lower=0, upper=100, step_increment=1), digits=0)
        editor_active = Gtk.CheckButton(label="Active")
        editor_time = Gtk.Label(xalign=0)

        # Place editor controls in grid
        right_box.attach(lbl_pass, 0, 0, 1, 1)
        right_box.attach(editor_pass, 1, 0, 1, 1)
        right_box.attach(lbl_speed, 0, 1, 1, 1)
        right_box.attach(editor_speed, 1, 1, 1, 1)
        right_box.attach(lbl_power, 0, 2, 1, 1)
        right_box.attach(editor_power, 1, 2, 1, 1)
        right_box.attach(editor_active, 0, 3, 2, 1)
        right_box.attach(lbl_time_lab, 0, 4, 1, 1)
        right_box.attach(editor_time, 1, 4, 1, 1)

        # Save/Cancel buttons
        btns = Gtk.ButtonBox(spacing=10)
        ok = Gtk.Button(label="Update Parameters")
        cancel = Gtk.Button(label="Cancel")
        btns.pack_start(ok, False, False, 0)
        btns.pack_start(cancel, False, False, 0)

        # Pack bottom widgets
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bottom_box.pack_start(summary_lbl, True, True, 0)
        bottom_box.pack_start(btns, False, False, 0)

        root_box.pack_start(bottom_box, False, False, 0)

        # Selection handling: when a row is selected, populate editor with that entry
        def on_row_selected(lb, row):
            if row is None:
                # clear editor
                editor_pass.set_value(1)
                editor_speed.set_value(0)
                editor_power.set_value(0)
                editor_active.set_active(False)
                editor_pass.set_sensitive(False)
                editor_speed.set_sensitive(False)
                editor_power.set_sensitive(False)
                editor_active.set_sensitive(False)
                editor_time.set_text("")
                return
            # find entry for row
            ent = next((e for e in entries if e['row'] is row), None)
            if ent is None:
                return
            editor_pass.set_sensitive(True)
            editor_speed.set_sensitive(True)
            editor_power.set_sensitive(True)
            editor_active.set_sensitive(True)
            editor_pass.set_value(ent['spin_p'].get_value())
            editor_speed.set_value(ent['spin_s'].get_value())
            editor_power.set_value(ent['spin_pw'].get_value())
            editor_active.set_active(ent['chk'].get_active())
            mins, engr, trav = compute_layer_minutes(ent)
            editor_time.set_text(human_time(mins)[0])

        listbox.connect('row-selected', on_row_selected)

        # When editor values change, reflect them into the selected entry
        def apply_editor_change(*_):
            sel = listbox.get_selected_row()
            if sel is None:
                return
            ent = next((e for e in entries if e['row'] is sel), None)
            if ent is None:
                return
            ent['spin_p'].set_value(editor_pass.get_value())
            ent['spin_s'].set_value(editor_speed.get_value())
            ent['spin_pw'].set_value(editor_power.get_value())
            ent['chk'].set_active(editor_active.get_active())
            update_row_summary(ent)
            update_global_summary()

        editor_pass.connect('value-changed', apply_editor_change)
        editor_speed.connect('value-changed', apply_editor_change)
        editor_power.connect('value-changed', apply_editor_change)
        editor_active.connect('toggled', apply_editor_change)

        # Initialize selection to first row
        if entries:
            listbox.show_all()
            listbox.select_row(entries[0]['row'])
            update_global_summary()

        ok.connect('clicked', self.save_and_exit, entries)
        cancel.connect('clicked', lambda _: Gtk.main_quit())

        window.add(root_box)
        window.show_all()
        Gtk.main()

    def save_and_exit(self, widget: Gtk.Button, entries: list[tuple]) -> None:
        """Save the layer parameters and exit the dialog."""
        # entries is a list of dicts created in the new UI: update each layer from widgets
        for ent in entries:
            layer = ent.get('layer')
            sp_p = ent.get('spin_p')
            sp_s = ent.get('spin_s')
            sp_pw = ent.get('spin_pw')
            chk = ent.get('chk')
            if layer is None:
                continue
            layer.set('data-passes', str(int(sp_p.get_value_as_int())))
            layer.set('data-speed', str(int(sp_s.get_value_as_int())))
            layer.set('data-power', str(int(sp_pw.get_value_as_int())))
            layer.set('data-active', 'true' if chk.get_active() else 'false')
        out = self.options.output  # This should be set by the extension framework
        etree.ElementTree(self.document.getroot()).write(out, xml_declaration=True,
                                                         encoding='utf-8', pretty_print=True)
        Gtk.main_quit()

if __name__ == '__main__':
    LayerDataDialog().run()
