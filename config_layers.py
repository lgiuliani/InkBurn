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
import math
from common import list_layers, get_layer_name, get_sorted_elements, get_element_points, get_element_subpaths

# GTK3 for the GUI
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

# Constants
DIST_UNIT = "mm"
TRAVEL_SPEED = 4000  # travel speed in mm/min for laser movement between objects
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
    def __init__(self):
        super().__init__()

    def layer_distance(self, layer: etree.Element) -> tuple[float, float]:
        """Calculate engrave and travel distances, accounting for subpaths"""
        elements = get_sorted_elements(layer)
        
        engrave = 0.0
        travel = 0.0
        
        last_point = (0.0, 0.0)  # Start from origin for first travel calculation
        
        for elem in elements:
            subpaths = get_element_subpaths(elem)
            if not subpaths:
                continue
            
            for subpath in subpaths:
                # Calculate engrave distance within this subpath
                for p1, p2 in zip(subpath[:-1], subpath[1:]):
                    engrave += math.dist(p1[1], p2[1])
                
                # Calculate travel to start of this subpath
                x0, y0 = subpath[0][1]
                travel += math.dist(last_point, (x0, y0))
                last_point = subpath[-1][1]  # Update to end of this subpath
        
        engrave = self.svg.unit_to_viewport(engrave, DIST_UNIT)
        travel = self.svg.unit_to_viewport(travel, DIST_UNIT)
        return engrave, travel
    
    def effect(self):
        svg = self.document.getroot()
        layers = list(list_layers(svg))
        if not layers:
            inkex.errormsg("No layers found.")
            return

        height = HEADER_HEIGHT + ROW_HEIGHT * (len(layers) + 1)
        height = min(height, MAX_HEIGHT)

        window = Gtk.Window(title="Ink/Burn : Configure layers")
        window.connect("delete-event", Gtk.main_quit)
        window.set_default_size(DEFAULT_WIDTH, height)

        vbox = Gtk.VBox(spacing=6, margin=12)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(scrolled, True, True, 0)
        grid = Gtk.Grid(row_spacing=6, column_spacing=10, margin=6)
        scrolled.add(grid)

        headers = ["<b>Layer</b>", "<b>Pass Count</b>", "<b>Speed</b> (mm/min)",
                   "<b>Power</b> (%)", "<b>Active</b>", "<b>Time</b>"]
        for c, txt in enumerate(headers):
            lbl_h = Gtk.Label(xalign=0)
            lbl_h.set_markup(txt)
            grid.attach(lbl_h, c, 0, 1, 1)

        entries, times = [], []
        summary_lbl = Gtk.Label(label="Total: 0:00:00", xalign=0)

        def update_summary():
            total = sum(t for a, t in times if a)
            human, _ = human_time(total)
            summary_lbl.set_text(f"Total: {human}")
            tooltip = "\n".join(
                f"{get_layer_name(layers[i])}: {times[i][1]:.1f}min"
                for i in range(len(times)) if times[i][0]
            )
            summary_lbl.set_tooltip_text(tooltip)

        def make_updater(i, spin_p, spin_s, chk, lbl_time, eng, trv):
            def upd(*args):
                cp = spin_p.get_value_as_int()
                cs = spin_s.get_value_as_int()
                engr = eng * cp
                trav = trv * cp
                e_min = (engr / cs) if cs > 0 else 0
                t_min = (trav / TRAVEL_SPEED)
                tot = e_min + t_min
                hstr, _ = human_time(tot)
                lbl_time.set_text(hstr)
                lbl_time.set_tooltip_text(f"Engrave: {engr:.1f}mm\nTravel: {trav:.1f}mm")
                times[i] = (chk.get_active(), tot)
                update_summary()
            return upd

        def on_active(btn, i, widgets):
            active = btn.get_active()
            for w in widgets:
                w.set_sensitive(active)
            times[i] = (active, times[i][1])
            update_summary()

        for idx, layer in enumerate(layers, start=1):
            name = get_layer_name(layer)
            p = int(layer.get('data-passes') or 1)
            s = int(layer.get('data-speed') or 0)
            pw = int(layer.get('data-power') or 0)
            act = layer.get('data-active') == 'true'
            eng, trv = self.layer_distance(layer)

            lbl = Gtk.Label(label=name, xalign=0)
            spin_p = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=p, lower=1, upper=20, step_increment=1, page_increment=5, page_size=0), digits=0)
            spin_s = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=s, lower=100, upper=10000, step_increment=100, page_increment=10, page_size=0), digits=0)
            spin_pw = Gtk.SpinButton(adjustment=Gtk.Adjustment(value=pw, lower=0, upper=100, step_increment=1, page_increment=10, page_size=0), digits=0)
            chk = Gtk.CheckButton()
            chk.set_active(act)
            lbl_time = Gtk.Label(xalign=0)
            times.append((act, 0.0))

            updater = make_updater(idx-1, spin_p, spin_s, chk, lbl_time, eng, trv)
            spin_p.connect('value-changed', updater)
            spin_s.connect('value-changed', updater)
            updater()
            for w in (lbl, spin_p, spin_s, spin_pw, lbl_time): w.set_sensitive(act)
            chk.connect('toggled', on_active, idx-1, [lbl, spin_p, spin_s, spin_pw, lbl_time])

            grid.attach(lbl,      0, idx, 1, 1)
            grid.attach(spin_p,   1, idx, 1, 1)
            grid.attach(spin_s,   2, idx, 1, 1)
            grid.attach(spin_pw,  3, idx, 1, 1)
            grid.attach(chk,      4, idx, 1, 1)
            grid.attach(lbl_time, 5, idx, 1, 1)
            entries.append((layer, spin_p, spin_s, spin_pw, chk))

        vbox.pack_start(summary_lbl, False, False, 0)

        btns = Gtk.ButtonBox(spacing=10)
        ok = Gtk.Button(label="Update Parameters")
        cancel = Gtk.Button(label="Cancel")
        btns.pack_start(ok, False, False, 0)
        btns.pack_start(cancel, False, False, 0)
        vbox.pack_start(btns, False, False, 0)

        ok.connect('clicked', self.save_and_exit, entries)
        cancel.connect('clicked', lambda _: Gtk.main_quit())

        window.add(vbox)
        window.show_all()
        Gtk.main()

    def save_and_exit(self, widget: Gtk.Button, entries: list[tuple]) -> None:
        """Save the layer parameters and exit the dialog."""
        for layer, sp_p, sp_s, sp_pw, chk in entries:
            layer.set('data-passes', str(int(sp_p.get_value())))
            layer.set('data-speed', str(int(sp_s.get_value())))
            layer.set('data-power', str(int(sp_pw.get_value())))
            layer.set('data-active', 'true' if chk.get_active() else 'false')
        out = self.options.output  # This should be set by the extension framework
        etree.ElementTree(self.document.getroot()).write(out, xml_declaration=True,
                                                         encoding='utf-8', pretty_print=True)
        Gtk.main_quit()

if __name__ == '__main__':
    LayerDataDialog().run()
