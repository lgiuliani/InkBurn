"""Path extraction from SVG elements.

Flattens SVG shapes into polyline segments suitable for G-code generation.
Handles Bézier subdivision, transforms, and Y-axis flipping.
"""

import logging
from typing import Dict, List

from inkex import bezier
from inkex.transforms import Transform, Vector2d
from lxml import etree

from constants import CLOSED_PATH_TOLERANCE, CURVE_PRECISION
from models.path import PathSegment, PathType, distance

logger = logging.getLogger(__name__)


class PathExtractor:
    """Extracts and processes paths from SVG elements.

    Attributes:
        curve_precision: Subdivision tolerance in mm for Bézier flattening.
    """

    def __init__(self, curve_precision: float = CURVE_PRECISION) -> None:
        """Initialize path extractor.

        Args:
            curve_precision: Precision for curve subdivision in mm.
        """
        self.curve_precision = curve_precision
        self._cache: Dict[str, List[PathSegment]] = {}

    def extract_from_element(
        self,
        element: etree._Element,
        viewbox_height: float,
    ) -> List[PathSegment]:
        """Extract path segments from an SVG element.

        Applies transforms, subdivides Bézier curves, and flips the
        Y axis so that output coordinates match machine space.

        Args:
            element: SVG element to process.
            viewbox_height: SVG viewbox height for Y-axis flip.

        Returns:
            List of PathSegment instances.
        """
        element_id = element.get("id", "")
        cache_key = f"{element_id}_{viewbox_height}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        segments = self._extract(element, element_id, viewbox_height)
        self._cache[cache_key] = segments
        return segments

    def clear_cache(self) -> None:
        """Clear the extraction cache."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract(
        self,
        element: etree._Element,
        element_id: str,
        viewbox_height: float,
    ) -> List[PathSegment]:
        """Core extraction logic.

        Args:
            element: SVG element.
            element_id: Element id attribute.
            viewbox_height: SVG viewbox height.

        Returns:
            List of PathSegment instances extracted from the element.
        """
        segments: List[PathSegment] = []

        transform = Transform(element.composed_transform())
        path = element.path.transform(transform)
        superpath = path.to_superpath()
        bezier.cspsubdiv(superpath, self.curve_precision)

        element_type = getattr(element, "tag_name", "unknown") or "unknown"

        for subpath in superpath:
            if not subpath or len(subpath) < 2:
                continue

            points = [
                Vector2d(pt[1][0], viewbox_height - pt[1][1])
                for pt in subpath
            ]

            is_closed = (
                len(points) > 2
                and distance(points[0], points[-1]) < CLOSED_PATH_TOLERANCE
            )

            segments.append(
                PathSegment(
                    points=points,
                    element_id=element_id,
                    element_type=element_type,
                    path_type=PathType.CLOSED if is_closed else PathType.OPEN,
                )
            )

        return segments
