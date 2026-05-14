"""G-code export extension for InkBurn.

Reads layer/job configuration from SVG ``data-job-X`` attributes,
processes each visible layer's active jobs in order, and writes a
single ``.nc`` file with GRBL 1.1 compatible G-code.
"""

from debug_utils import debug_output
from models import DebugLevel, MachineSettings
import logging
import subprocess
from pathlib import Path
from sys import platform
from typing import Dict, List, Optional, Tuple

import inkex
from lxml import etree

from common import get_image_elements, get_visible_shapes, is_visible, list_layers
from gcode.generator import GCodeGenerator
from geometry.extractor import PathExtractor
from geometry.hatching import generate_hatch_lines_for_polygons
from geometry.optimizer import PathOptimizer
from models.job import Job, JobType
from models.layer import Layer
from models.path import OptimizationMetrics, PathSegment, PathType
from persistence.preferences import load_machine_settings
from persistence.svg_io import load_layers
from raster.processor import RasterProcessor

logger = logging.getLogger(__name__)


def _parse_style(style: str) -> Dict[str, str]:
    """Parse an inline SVG style attribute into lowercase property names."""
    declarations: Dict[str, str] = {}
    for declaration in style.split(";"):
        if ":" not in declaration:
            continue
        name, value = declaration.split(":", 1)
        declarations[name.strip().lower()] = value.strip()
    return declarations


def _local_style_property(elem: etree._Element, name: str) -> Optional[str]:
    """Read a style property from inline CSS or a presentation attribute."""
    name = name.lower()
    value = _parse_style(elem.get("style") or "").get(name)
    if value is not None:
        return value
    return elem.get(name)


def _inherited_style_property(elem: etree._Element, name: str) -> Optional[str]:
    """Resolve a simple inherited SVG style property from element ancestors."""
    for current in [elem, *elem.iterancestors()]:
        value = _local_style_property(current, name)
        if value is not None:
            return value
    return None


def _parse_opacity(value: Optional[str]) -> Optional[float]:
    """Parse an SVG opacity value, returning None when it is not numeric."""
    if value is None:
        return None

    value = value.strip()
    try:
        if value.endswith("%"):
            return float(value[:-1]) / 100.0
        return float(value)
    except ValueError:
        return None


def _is_transparent_paint(value: str) -> bool:
    """Return True when an SVG paint value represents no visible paint."""
    normalized = value.strip().lower().replace(" ", "")
    if normalized in {"none", "transparent"}:
        return True
    if normalized.startswith("#") and len(normalized) in {5, 9}:
        return normalized[-2:] == "00"
    if normalized.startswith(
        ("rgb(", "rgba(", "hsl(", "hsla(")
    ) and normalized.endswith(")"):
        body = normalized.split("(", 1)[1][:-1]
        if "/" in body:
            alpha = body.rsplit("/", 1)[-1]
        elif normalized.startswith(("rgba(", "hsla(")):
            alpha = body.rsplit(",", 1)[-1]
        else:
            return False
        return _parse_opacity(alpha) == 0
    return False


def _has_visible_fill(elem: etree._Element) -> bool:
    """Check whether an element has a fill color visible enough to hatch."""
    fill = _inherited_style_property(elem, "fill")
    if fill is not None and _is_transparent_paint(fill):
        return False

    fill_opacity = _parse_opacity(_inherited_style_property(elem, "fill-opacity"))
    if fill_opacity == 0:
        return False

    for current in [elem, *elem.iterancestors()]:
        opacity = _parse_opacity(_local_style_property(current, "opacity"))
        if opacity == 0:
            return False

    return True


def _fill_rule(elem: etree._Element) -> str:
    """Resolve the SVG fill rule used to hatch a filled element."""
    value = _inherited_style_property(elem, "fill-rule")
    if value is None:
        return "nonzero"

    normalized = value.strip().lower().replace("-", "")
    return "evenodd" if normalized == "evenodd" else "nonzero"


def _open_file(filename: str) -> None:
    """Open a file with the system default application.

    Args:
        filename: Path to the file to open.
    """
    if platform == "win32":
        from os import startfile  # type: ignore[attr-defined]

        startfile(filename)
    else:
        opener = "open" if platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])


class ExportGCode(inkex.OutputExtension):
    """Inkscape extension that exports SVG layers/jobs to G-code.

    Processes layers in SVG document order.  For each visible layer,
    active jobs are executed in their defined order.
    """

    def __init__(self) -> None:
        """Initialize exporter."""
        super().__init__()
        self._settings = load_machine_settings()
        self._extractor = PathExtractor()
        self._generator = GCodeGenerator(self._settings)

    def save(self, stream: object) -> None:
        """Generate and save G-code.

        Args:
            stream: Output stream (unused — we write to file directly).
        """
        self.preprocess()

        svg = self.document.getroot()
        viewbox_height = svg.viewbox_height
        doc_name = Path(self.document_path() or "untitled.svg").stem

        self._generator.reset()
        self._generator.add_header(document_name=doc_name)

        layers, elements = load_layers(svg)
        total_metrics = OptimizationMetrics()

        for layer in layers:
            elem = elements.get(layer.layer_id)
            if elem is None or not is_visible(elem):
                continue
            if not layer.jobs:
                continue

            self._process_layer(layer, elem, viewbox_height, total_metrics)

        self._generator.add_footer()

        # Write output
        output_path = Path(self.document_path() or "output").with_suffix(".nc")
        output_path.write_text(self._generator.get_gcode(), encoding="utf-8")

        # Log optimization summary
        if self._settings.path_optimization and total_metrics.original_travel_distance > 0:
            debug_output(
                self._settings,
                f"\n=== Optimization Summary ===\n"
                f"Travel reduced: {total_metrics.travel_savings:.1f}%\n"
                f"Original: {total_metrics.original_travel_distance:.1f}mm\n"
                f"Optimized: {total_metrics.optimized_travel_distance:.1f}mm\n"
                f"Paths reversed: {total_metrics.paths_reversed}",
                DebugLevel.INFO,
            )

        # Autolaunch
        if self._settings.autolaunch:
            try:
                _open_file(str(output_path))
            except Exception as exc:
                debug_output(
                    self._settings,
                    f"Autolaunch failed: {exc}",
                    DebugLevel.CRITICAL,
                )

    # ------------------------------------------------------------------
    # Layer processing
    # ------------------------------------------------------------------

    def _process_layer(
        self,
        layer: Layer,
        elem: etree._Element,
        viewbox_height: float,
        total_metrics: OptimizationMetrics,
    ) -> None:
        """Process all active jobs for a single layer.

        Args:
            layer: Layer model.
            elem: SVG ``<g>`` element.
            viewbox_height: SVG viewbox height.
            total_metrics: Accumulated optimization metrics.
        """
        active_jobs = layer.active_jobs()
        if not active_jobs:
            return

        for idx, job in enumerate(active_jobs):
            if job.type == JobType.CUT:
                self._process_cut_job(
                    layer, elem, job, idx, viewbox_height, total_metrics
                )
            elif job.type == JobType.FILL:
                self._process_fill_job(
                    layer, elem, job, idx, viewbox_height, total_metrics
                )
            elif job.type == JobType.RASTER:
                self._process_raster_job(
                    layer, elem, job, idx, viewbox_height
                )

    def _process_cut_job(
        self,
        layer: Layer,
        elem: etree._Element,
        job: Job,
        job_index: int,
        viewbox_height: float,
        total_metrics: OptimizationMetrics,
    ) -> None:
        """Process a cut (contour) job.

        Args:
            layer: Parent layer.
            elem: SVG layer element.
            job: Cut job configuration.
            job_index: Job position for comments.
            viewbox_height: SVG viewbox height.
            total_metrics: Accumulated metrics.
        """
        segments = self._extract_segments(elem, viewbox_height)
        if not segments:
            return

        segments = self._optimize_segments(segments, layer.label, total_metrics)
        self._generator.add_comment(f"Layer: {layer.label}")
        self._generator.add_job(segments, job, job_index)

    def _process_fill_job(
        self,
        layer: Layer,
        elem: etree._Element,
        job: Job,
        job_index: int,
        viewbox_height: float,
        total_metrics: OptimizationMetrics,
    ) -> None:
        """Process a fill (hatching) job.

        Args:
            layer: Parent layer.
            elem: SVG layer element.
            job: Fill job configuration.
            job_index: Job position for comments.
            viewbox_height: SVG viewbox height.
            total_metrics: Accumulated metrics.
        """
        segment_groups = self._extract_fill_segment_groups(elem, viewbox_height)
        if not segment_groups:
            return

        angle = float(job.params.get("angle", 45.0))
        spacing = float(job.params.get("spacing", 0.5))
        alternate = bool(job.params.get("alternate", True))

        hatch_segments: List[PathSegment] = []
        for shape, segments in segment_groups:
            closed_polygons = [
                seg.points
                for seg in segments
                if seg.path_type is PathType.CLOSED and len(seg.points) >= 3
            ]
            if not closed_polygons:
                continue

            hatches = generate_hatch_lines_for_polygons(
                closed_polygons,
                angle=angle,
                spacing=spacing,
                alternate=alternate,
                fill_rule=_fill_rule(shape),
            )
            hatch_segments.extend(hatches)

        if not hatch_segments:
            debug_output(
                self._settings,
                f"Layer '{layer.label}': No closed paths for fill job",
                DebugLevel.WARNING,
            )
            return

        hatch_segments = self._optimize_segments(
            hatch_segments, layer.label, total_metrics
        )
        self._generator.add_comment(f"Layer: {layer.label}")
        self._generator.add_job(hatch_segments, job, job_index)

    def _process_raster_job(
        self,
        layer: Layer,
        elem: etree._Element,
        job: Job,
        job_index: int,
        viewbox_height: float,
    ) -> None:
        """Process a raster job.

        Args:
            layer: Parent layer.
            elem: SVG layer element.
            job: Raster job configuration.
            job_index: Job position for comments.
            viewbox_height: SVG viewbox height.
        """
        images = get_image_elements(elem)
        if not images:
            debug_output(
                self._settings,
                f"Layer '{layer.label}': No images for raster job",
                DebugLevel.WARNING,
            )
            return

        dpi = int(job.params.get("dpi", 300))
        direction = str(job.params.get("direction", "horizontal"))
        processor = RasterProcessor(dpi=dpi, direction=direction)

        self._generator.add_comment(f"Layer: {layer.label}")
        self._generator.add_comment(
            f"Job: {job.type.value} {job_index} (id={job.id})"
        )

        for img_elem in images:
            scanlines = processor.process_image_element(
                img_elem, viewbox_height, job
            )
            speed = self._settings.clamp_speed(job.speed)
            for segment, power_list in scanlines:
                self._generator.add_shape_comment(segment)
                self._generator.move_to(segment.start_point, is_cutting=False)
                self._generator.enable_laser(job.laser_mode.value, power_list[0])
                
                # Emit G1 with per-pixel S values
                for i, point in enumerate(segment.points[1:], start=1):
                    power = power_list[i]
                    self._generator.move_to(
                        point, is_cutting=True, speed=speed, power=power
                    )
                
                self._generator.disable_laser()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_segments(
        self, elem: etree._Element, viewbox_height: float
    ) -> List[PathSegment]:
        """Extract path segments from all shapes in a layer element.

        Args:
            elem: SVG layer element.
            viewbox_height: SVG viewbox height.

        Returns:
            List of path segments.
        """
        segments: List[PathSegment] = []
        for shape in get_visible_shapes(elem):
            extracted = self._extractor.extract_from_element(shape, viewbox_height)
            segments.extend(extracted)
        return segments

    def _extract_fill_segment_groups(
        self, elem: etree._Element, viewbox_height: float
    ) -> List[Tuple[etree._Element, List[PathSegment]]]:
        """Extract path segments grouped by filled SVG element."""
        segment_groups: List[Tuple[etree._Element, List[PathSegment]]] = []
        for shape in get_visible_shapes(elem):
            if not _has_visible_fill(shape):
                continue
            extracted = self._extractor.extract_from_element(shape, viewbox_height)
            if extracted:
                segment_groups.append((shape, extracted))
        return segment_groups

    def _optimize_segments(
        self,
        segments: List[PathSegment],
        label: str,
        total_metrics: OptimizationMetrics,
    ) -> List[PathSegment]:
        """Optionally optimize segment order via nearest-neighbor.

        Args:
            segments: Segments to optimize.
            label: Layer label for debug output.
            total_metrics: Accumulated optimization metrics.

        Returns:
            Optimized segment list.
        """
        if not self._settings.path_optimization:
            return segments

        optimizer = PathOptimizer()
        optimized, metrics = optimizer.optimize(
            segments,
            enable_direction_optimization=self._settings.direction_optimization,
        )

        total_metrics.original_travel_distance += metrics.original_travel_distance
        total_metrics.optimized_travel_distance += metrics.optimized_travel_distance
        total_metrics.paths_reversed += metrics.paths_reversed

        debug_output(
            self._settings,
            f"Layer '{label}': Travel reduced by {metrics.travel_savings:.1f}% "
            f"({metrics.paths_reversed} paths reversed)",
            DebugLevel.INFO,
        )

        return optimized


if __name__ == "__main__":
    ExportGCode().run()
