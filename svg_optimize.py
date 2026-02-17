"""Inkscape extension entry point — SVG Optimization.

Reorders SVG shape elements inside each layer using a nearest-neighbor
heuristic to minimize laser travel distance, without changing
object types or layer membership.
"""

import inkex
from inkex.transforms import Vector2d
from lxml import etree

from common import get_visible_shapes, is_visible, list_layers
from geometry.extractor import PathExtractor
from geometry.optimizer import PathOptimizer
from models.path import PathSegment


class SvgOptimize(inkex.EffectExtension):
    """Inkscape effect that reorders SVG elements for optimal laser path."""

    def effect(self) -> None:
        """Reorder elements in each visible layer."""
        svg = self.document.getroot()
        viewbox_height = svg.viewbox_height
        extractor = PathExtractor()

        total_reordered = 0

        for layer_elem in list_layers(svg):
            if not is_visible(layer_elem):
                continue

            elements = get_visible_shapes(layer_elem)
            if len(elements) < 2:
                continue

            elem_segments: list[tuple[etree._Element, PathSegment]] = []
            for elem in elements:
                segs = extractor.extract_from_element(elem, viewbox_height)
                if segs:
                    elem_segments.append((elem, segs[0]))

            if len(elem_segments) < 2:
                continue

            segments = [seg for _, seg in elem_segments]
            optimizer = PathOptimizer()
            optimized, metrics = optimizer.optimize(segments)

            # Build reorder mapping
            original_ids = [seg.element_id for seg in segments]
            optimized_ids = [seg.element_id for seg in optimized]

            if original_ids == optimized_ids:
                continue

            elem_by_id = {e.get("id"): e for e, _ in elem_segments}
            # Reorder: remove and re-append in optimized order
            for opt_seg in optimized:
                elem = elem_by_id.get(opt_seg.element_id)
                if elem is not None:
                    parent = elem.getparent()
                    if parent is not None:
                        parent.remove(elem)
                        parent.append(elem)

            total_reordered += len(optimized)

            inkex.utils.debug(
                f"Reordered {len(optimized)} elements: "
                f"travel reduced by {metrics.travel_savings:.1f}%"
            )

        if total_reordered == 0:
            inkex.utils.debug("No reordering needed.")


if __name__ == "__main__":
    SvgOptimize().run()
