"""G-code export extension for InkBurn.

Reads layer/job configuration from SVG ``data-job-X`` attributes,
processes each visible layer's active jobs in order, and writes a
single ``.nc`` file with GRBL 1.1 compatible G-code.
"""

import logging
import subprocess
from pathlib import Path
from sys import platform
from typing import List, Tuple

import inkex
from lxml import etree

from svg_layers import get_image_elements, get_visible_shapes, is_visible
from debug_utils import debug_output
from gcode.generator import GCodeGenerator
from geometry.extractor import PathExtractor
from geometry.hatching import generate_hatch_lines_for_polygons
from geometry.optimizer import PathOptimizer
from models import DebugLevel
from models.job import Job, JobType
from models.layer import Layer
from models.path import OptimizationMetrics, PathSegment, PathType
from persistence.preferences import load_machine_settings
from persistence.svg_io import load_layers
from raster.processor import RasterProcessor
from svg_style import (
    apply_fill_power_to_hatch,
    fill_rule,
    has_visible_fill,
    polygons_svg_bbox,
)

logger = logging.getLogger(__name__)


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
            stream: Output stream (unused; we write to file directly).
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

        output_path = Path(self.document_path() or "output").with_suffix(".nc")
        output_path.write_text(self._generator.get_gcode(), encoding="utf-8")

        self._log_optimization_summary(total_metrics)
        self._autolaunch_output(output_path)

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
        """Process all active jobs for a single layer."""
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
                self._process_raster_job(layer, elem, job, idx, viewbox_height)

    def _process_cut_job(
        self,
        layer: Layer,
        elem: etree._Element,
        job: Job,
        job_index: int,
        viewbox_height: float,
        total_metrics: OptimizationMetrics,
    ) -> None:
        """Process a cut (contour) job."""
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
        """Process a fill (hatching) job."""
        segment_groups = self._extract_fill_segment_groups(elem, viewbox_height)
        if not segment_groups:
            return

        hatch_segments = self._build_hatch_segments(
            segment_groups,
            job,
            viewbox_height,
        )
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
        """Process a raster job."""
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

        segments: List[PathSegment] = []
        for img_elem in images:
            segments.extend(
                processor.process_image_element(img_elem, viewbox_height, job)
            )

        self._generator.add_comment(f"Layer: {layer.label}")
        self._generator.add_job(segments, job, job_index)

    # ------------------------------------------------------------------
    # Fill construction
    # ------------------------------------------------------------------

    def _build_hatch_segments(
        self,
        segment_groups: List[Tuple[etree._Element, List[PathSegment]]],
        job: Job,
        viewbox_height: float,
    ) -> List[PathSegment]:
        """Build hatch segments from grouped filled shapes."""
        angle = float(job.params.get("angle", 45.0))
        spacing = float(job.params.get("spacing", 0.5))
        alternate = bool(job.params.get("alternate", True))
        gradient_sample_step = max(
            self._settings.resolution,
            min(spacing, 1.0),
        )

        hatch_segments: List[PathSegment] = []
        for shape, segments in segment_groups:
            closed_polygons = [
                seg.points
                for seg in segments
                if seg.path_type is PathType.CLOSED and len(seg.points) >= 3
            ]
            if not closed_polygons:
                continue

            bbox = polygons_svg_bbox(closed_polygons, viewbox_height)
            hatches = generate_hatch_lines_for_polygons(
                closed_polygons,
                angle=angle,
                spacing=spacing,
                alternate=alternate,
                fill_rule=fill_rule(shape),
            )
            self._assign_hatch_metadata(
                hatches,
                shape,
                job,
                viewbox_height,
                bbox,
                gradient_sample_step,
            )
            hatch_segments.extend(hatches)

        return hatch_segments

    def _assign_hatch_metadata(
        self,
        hatches: List[PathSegment],
        shape: etree._Element,
        job: Job,
        viewbox_height: float,
        bbox: Tuple[float, float, float, float],
        gradient_sample_step: float,
    ) -> None:
        """Attach shape identity and fill power to generated hatches."""
        shape_id = shape.get("id") or "hatch"
        shape_type = getattr(shape, "tag_name", "hatch") or "hatch"

        for hatch in hatches:
            hatch.element_id = shape_id
            hatch.element_type = shape_type
            apply_fill_power_to_hatch(
                hatch,
                shape,
                job,
                viewbox_height,
                bbox,
                gradient_sample_step,
            )

    # ------------------------------------------------------------------
    # Extraction / optimization helpers
    # ------------------------------------------------------------------

    def _extract_segments(
        self, elem: etree._Element, viewbox_height: float
    ) -> List[PathSegment]:
        """Extract path segments from all shapes in a layer element."""
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
            if not has_visible_fill(shape):
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
        """Optionally optimize segment order via nearest-neighbor."""
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

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _log_optimization_summary(self, total_metrics: OptimizationMetrics) -> None:
        """Log a cumulative path optimization summary when available."""
        if (
            not self._settings.path_optimization
            or total_metrics.original_travel_distance <= 0
        ):
            return

        debug_output(
            self._settings,
            f"\n=== Optimization Summary ===\n"
            f"Travel reduced: {total_metrics.travel_savings:.1f}%\n"
            f"Original: {total_metrics.original_travel_distance:.1f}mm\n"
            f"Optimized: {total_metrics.optimized_travel_distance:.1f}mm\n"
            f"Paths reversed: {total_metrics.paths_reversed}",
            DebugLevel.INFO,
        )

    def _autolaunch_output(self, output_path: Path) -> None:
        """Open generated output when autolaunch is enabled."""
        if not self._settings.autolaunch:
            return

        try:
            _open_file(str(output_path))
        except Exception as exc:
            debug_output(
                self._settings,
                f"Autolaunch failed: {exc}",
                DebugLevel.CRITICAL,
            )


if __name__ == "__main__":
    ExportGCode().run()
