"""GTK UI manager for layer/job configuration dialog.

Provides a left panel with an ordered layer list and a right panel
with job management controls (add/remove/reorder/edit).
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from typing import Dict, List, Optional

from config_core.helpers import (
    PARAM_SCHEMA,
    make_labeled_check,
    make_labeled_combo,
    make_labeled_spin,
)
from models.job import Job, JobType, LaserMode
from models.layer import Layer


class UIManager:
    """Manage the GTK UI, wiring widgets to the Layer/Job models."""

    def __init__(
        self,
        layers: List[Layer],
        elements: Dict[str, object],
    ) -> None:
        """Initialize the UI manager and build the GTK window.

        Args:
            layers: Ordered list of layers from SVG.
            elements: Mapping of layer_id → SVG element.
        """
        self.layers = layers
        self.elements = elements
        self._current_layer_idx: Optional[int] = None
        self._current_job_idx: Optional[int] = None
        self._param_widgets: Dict[str, object] = {}

        self._build_window()
        self._populate_layer_list()

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------

    def _build_window(self) -> None:
        """Build the main GTK window with layer and job panels."""
        self.window = Gtk.Window(title="Ink/Burn : Layer & Job Configuration")
        self.window.set_default_size(900, 600)

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin=8)

        # Left: layer list
        left_frame = Gtk.Frame(label="Layers")
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin=4)
        self._layer_store = Gtk.ListStore(str, str, str, bool)
        self._layer_tv = Gtk.TreeView(model=self._layer_store)
        self._setup_layer_columns()
        scroll_layers = Gtk.ScrolledWindow()
        scroll_layers.set_min_content_width(250)
        scroll_layers.add(self._layer_tv)
        left_box.pack_start(scroll_layers, True, True, 0)
        left_frame.add(left_box)
        main_box.pack_start(left_frame, False, True, 0)

        # Right: jobs + detail
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Job list
        job_frame = Gtk.Frame(label="Jobs")
        job_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin=4)
        self._job_store = Gtk.ListStore(str, str, bool)
        self._job_tv = Gtk.TreeView(model=self._job_store)
        self._setup_job_columns()
        scroll_jobs = Gtk.ScrolledWindow()
        scroll_jobs.set_min_content_height(150)
        scroll_jobs.add(self._job_tv)
        job_box.pack_start(scroll_jobs, True, True, 0)

        # Job buttons
        btn_bar = Gtk.Box(spacing=4)
        btn_add_cut = Gtk.Button(label="+ Cut")
        btn_add_fill = Gtk.Button(label="+ Fill")
        btn_add_raster = Gtk.Button(label="+ Raster")
        btn_remove = Gtk.Button(label="— Remove")
        btn_up = Gtk.Button(label="↑ Up")
        btn_down = Gtk.Button(label="↓ Down")
        for btn in (btn_add_cut, btn_add_fill, btn_add_raster, btn_remove, btn_up, btn_down):
            btn_bar.pack_start(btn, False, False, 0)
        btn_add_cut.connect("clicked", lambda _: self._add_job(JobType.CUT))
        btn_add_fill.connect("clicked", lambda _: self._add_job(JobType.FILL))
        btn_add_raster.connect("clicked", lambda _: self._add_job(JobType.RASTER))
        btn_remove.connect("clicked", lambda _: self._remove_job())
        btn_up.connect("clicked", lambda _: self._move_job(-1))
        btn_down.connect("clicked", lambda _: self._move_job(1))
        job_box.pack_start(btn_bar, False, False, 0)
        job_frame.add(job_box)
        right_box.pack_start(job_frame, False, True, 0)

        # Job detail area
        detail_frame = Gtk.Frame(label="Job Parameters")
        self._detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin=8)
        detail_scroll = Gtk.ScrolledWindow()
        detail_scroll.add(self._detail_box)
        detail_frame.add(detail_scroll)
        right_box.pack_start(detail_frame, True, True, 0)

        # Bottom buttons
        bottom_bar = Gtk.Box(spacing=8, margin=4)
        btn_save = Gtk.Button(label="Save & Close")
        btn_close = Gtk.Button(label="Cancel")
        btn_save.connect("clicked", self._on_save)
        btn_close.connect("clicked", self._on_close)
        bottom_bar.pack_end(btn_close, False, False, 0)
        bottom_bar.pack_end(btn_save, False, False, 0)
        right_box.pack_start(bottom_bar, False, False, 0)

        main_box.pack_start(right_box, True, True, 0)
        self.window.add(main_box)

        # Connect selection signals
        self._layer_tv.get_selection().connect("changed", self._on_layer_selected)
        self._job_tv.get_selection().connect("changed", self._on_job_selected)

        self.saved = False

    # ------------------------------------------------------------------
    # Layer columns & population
    # ------------------------------------------------------------------

    def _setup_layer_columns(self) -> None:
        """Set up columns for the layer treeview."""
        rend_name = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Layer", rend_name, text=1)
        col_name.set_expand(True)
        self._layer_tv.append_column(col_name)

        rend_summary = Gtk.CellRendererText()
        col_summary = Gtk.TreeViewColumn("Info", rend_summary, text=2)
        self._layer_tv.append_column(col_summary)

    def _populate_layer_list(self) -> None:
        """Fill layer store from model data."""
        self._layer_store.clear()
        for layer in self.layers:
            vis_marker = "" if layer.visible else "  (hidden)"
            self._layer_store.append([
                layer.layer_id,
                layer.label + vis_marker,
                layer.get_summary(),
                layer.visible,
            ])

    # ------------------------------------------------------------------
    # Job columns & population
    # ------------------------------------------------------------------

    def _setup_job_columns(self) -> None:
        """Set up columns for the job treeview."""
        rend_toggle = Gtk.CellRendererToggle()
        rend_toggle.set_property("activatable", True)
        rend_toggle.connect("toggled", self._on_job_toggle_active)
        col_active = Gtk.TreeViewColumn("On", rend_toggle, active=2)
        self._job_tv.append_column(col_active)

        rend_type = Gtk.CellRendererText()
        col_type = Gtk.TreeViewColumn("Type", rend_type, text=0)
        self._job_tv.append_column(col_type)

        rend_summary = Gtk.CellRendererText()
        col_summary = Gtk.TreeViewColumn("Summary", rend_summary, text=1)
        col_summary.set_expand(True)
        self._job_tv.append_column(col_summary)

    def _populate_job_list(self) -> None:
        """Fill job store from the currently selected layer."""
        self._job_store.clear()
        self._current_job_idx = None
        self._clear_detail()

        layer = self._current_layer()
        if layer is None:
            return

        for job in layer.jobs:
            self._job_store.append([
                job.type.value.capitalize(),
                job.get_summary(),
                job.active,
            ])

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_layer_selected(self, selection: Gtk.TreeSelection) -> None:
        """Handle layer selection change."""
        model, it = selection.get_selected()
        if not it:
            return
        path = model.get_path(it)
        self._current_layer_idx = path.get_indices()[0]
        self._populate_job_list()

    def _on_job_selected(self, selection: Gtk.TreeSelection) -> None:
        """Handle job selection change."""
        model, it = selection.get_selected()
        if not it:
            return
        path = model.get_path(it)
        self._current_job_idx = path.get_indices()[0]
        self._build_detail_form()

    def _on_job_toggle_active(self, renderer: object, path: str) -> None:
        """Toggle a job's active state."""
        row = self._job_store[path]
        row[2] = not row[2]
        layer = self._current_layer()
        if layer is None:
            return
        idx = int(path)
        if 0 <= idx < len(layer.jobs):
            layer.jobs[idx].active = row[2]
            row[1] = layer.jobs[idx].get_summary()
            self._update_layer_summary()

    def _on_save(self, _button: object) -> None:
        """Save and close the dialog."""
        self.saved = True
        self.window.destroy()

    def _on_close(self, _button: object) -> None:
        """Close without saving."""
        self.window.destroy()

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def _add_job(self, job_type: JobType) -> None:
        """Add a new job to the current layer."""
        layer = self._current_layer()
        if layer is None:
            return
        layer.add_job(job_type)
        self._populate_job_list()
        self._update_layer_summary()

    def _remove_job(self) -> None:
        """Remove the selected job."""
        layer = self._current_layer()
        if layer is None or self._current_job_idx is None:
            return
        layer.remove_job(self._current_job_idx)
        self._current_job_idx = None
        self._populate_job_list()
        self._update_layer_summary()

    def _move_job(self, direction: int) -> None:
        """Move the selected job up (-1) or down (+1)."""
        layer = self._current_layer()
        if layer is None or self._current_job_idx is None:
            return
        idx = self._current_job_idx
        if direction < 0:
            moved = layer.move_job_up(idx)
            new_idx = idx - 1 if moved else idx
        else:
            moved = layer.move_job_down(idx)
            new_idx = idx + 1 if moved else idx

        self._populate_job_list()
        if moved:
            self._current_job_idx = new_idx
            self._job_tv.get_selection().select_path(Gtk.TreePath(new_idx))

    # ------------------------------------------------------------------
    # Job detail form
    # ------------------------------------------------------------------

    def _clear_detail(self) -> None:
        """Remove all widgets from the detail panel."""
        for child in self._detail_box.get_children():
            self._detail_box.remove(child)
        self._param_widgets.clear()

    def _build_detail_form(self) -> None:
        """Build the parameter form for the selected job."""
        self._clear_detail()

        job = self._current_job()
        if job is None:
            return

        # Job type (read-only label)
        type_lbl = Gtk.Label(xalign=0)
        type_lbl.set_markup(f"<b>Type:</b> {job.type.value.capitalize()}")
        self._detail_box.pack_start(type_lbl, False, False, 0)

        # Laser mode combo
        box_lm, combo_lm = make_labeled_combo("Laser mode", [
            ("M3", "M3 (Constant Power)"),
            ("M4", "M4 (Dynamic Power)"),
        ])
        combo_lm.set_active_id(job.laser_mode.value)
        combo_lm.connect("changed", self._on_laser_mode_changed)
        self._detail_box.pack_start(box_lm, False, False, 0)

        # Air assist checkbox
        box_air, chk_air = make_labeled_check("Air assist")
        chk_air.set_active(job.air_assist)
        chk_air.connect("toggled", lambda w: self._update_job_field("air_assist", w.get_active()))
        self._detail_box.pack_start(box_air, False, False, 0)

        # Type-specific parameters
        schema = PARAM_SCHEMA.get(job.type, [])
        for name, label, ptype, min_v, max_v, step in schema:
            if ptype is bool:
                box, widget = make_labeled_check(label)
                val = job.params.get(name, False)
                widget.set_active(bool(val))
                widget.connect("toggled", lambda w, n=name: self._on_param_changed_bool(w, n))
                self._param_widgets[name] = widget
            elif ptype is str:
                options = [("horizontal", "Horizontal"), ("vertical", "Vertical")]
                box, widget = make_labeled_combo(label, options)
                widget.set_active_id(str(job.params.get(name, "horizontal")))
                widget.connect("changed", lambda w, n=name: self._on_param_changed_combo(w, n))
                self._param_widgets[name] = widget
            else:
                box, widget = make_labeled_spin(label, min_v, max_v, step)
                val = self._get_job_value(job, name)
                widget.set_value(float(val))
                if ptype is int:
                    widget.set_digits(0)
                widget.connect("value-changed", lambda w, n=name, t=ptype: self._on_param_changed(w, n, t))
                self._param_widgets[name] = widget
            self._detail_box.pack_start(box, False, False, 0)

        self._detail_box.show_all()

    def _get_job_value(self, job: Job, name: str) -> float:
        """Get a numeric value from a job, checking top-level attrs first.

        Args:
            job: Job to read from.
            name: Parameter name.

        Returns:
            Value as float.
        """
        if hasattr(job, name):
            return float(getattr(job, name))
        return float(job.params.get(name, 0))

    def _on_laser_mode_changed(self, combo: Gtk.ComboBoxText) -> None:
        """Handle laser mode combo change."""
        job = self._current_job()
        if job is None:
            return
        val = combo.get_active_id()
        if val:
            job.laser_mode = LaserMode(val)
            self._refresh_job_row()

    def _on_param_changed(self, widget: Gtk.SpinButton, name: str, ptype: type) -> None:
        """Handle spin button value change."""
        job = self._current_job()
        if job is None:
            return
        val = int(widget.get_value()) if ptype is int else widget.get_value()
        self._update_job_field(name, val)

    def _on_param_changed_bool(self, widget: Gtk.CheckButton, name: str) -> None:
        """Handle check button toggle."""
        job = self._current_job()
        if job is None:
            return
        self._update_job_field(name, widget.get_active())

    def _on_param_changed_combo(self, widget: Gtk.ComboBoxText, name: str) -> None:
        """Handle combo box change."""
        job = self._current_job()
        if job is None:
            return
        val = widget.get_active_id()
        if val:
            self._update_job_field(name, val)

    def _update_job_field(self, name: str, value: object) -> None:
        """Update a field on the current job.

        Args:
            name: Field or param key name.
            value: New value.
        """
        job = self._current_job()
        if job is None:
            return
        if hasattr(job, name) and name not in ("params", "type", "id"):
            setattr(job, name, value)
        else:
            job.params[name] = value
        self._refresh_job_row()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_layer(self) -> Optional[Layer]:
        """Return the currently selected layer or None."""
        if self._current_layer_idx is None:
            return None
        if 0 <= self._current_layer_idx < len(self.layers):
            return self.layers[self._current_layer_idx]
        return None

    def _current_job(self) -> Optional[Job]:
        """Return the currently selected job or None."""
        layer = self._current_layer()
        if layer is None or self._current_job_idx is None:
            return None
        if 0 <= self._current_job_idx < len(layer.jobs):
            return layer.jobs[self._current_job_idx]
        return None

    def _refresh_job_row(self) -> None:
        """Update the summary text of the current job row."""
        job = self._current_job()
        if job is None or self._current_job_idx is None:
            return
        row = self._job_store[self._current_job_idx]
        row[1] = job.get_summary()
        self._update_layer_summary()

    def _update_layer_summary(self) -> None:
        """Refresh the layer summary in the layer list."""
        if self._current_layer_idx is None:
            return
        layer = self._current_layer()
        if layer is None:
            return
        row = self._layer_store[self._current_layer_idx]
        row[2] = layer.get_summary()
