"""Vector hatching (fill) algorithm for InkBurn extension.

Generates parallel hatch lines inside a closed polygon, used by
fill-type laser jobs to engrave the interior of shapes.
"""

import math
from typing import List, Optional, Tuple

from inkex.transforms import Vector2d

from models.path import PathSegment, PathType


def generate_hatch_lines(
    polygon: List[Vector2d],
    angle: float = 45.0,
    spacing: float = 0.5,
    alternate: bool = True,
) -> List[PathSegment]:
    """Generate parallel hatch lines inside a polygon.

    Uses a scanline approach: rotates the polygon by ``-angle``, casts
    horizontal scanlines at ``spacing`` intervals, intersects them with
    polygon edges, then rotates the intersection points back.

    Args:
        polygon: Ordered list of 2-D vertices forming a closed polygon.
        angle: Hatch angle in degrees (0 = horizontal).
        spacing: Distance between hatch lines in mm.
        alternate: If True, alternate directions for smoother travel.

    Returns:
        List of PathSegment instances representing hatch lines.
    """
    return generate_hatch_lines_for_polygons(
        [polygon],
        angle=angle,
        spacing=spacing,
        alternate=alternate,
    )


def generate_hatch_lines_for_polygons(
    polygons: List[List[Vector2d]],
    angle: float = 45.0,
    spacing: float = 0.5,
    alternate: bool = True,
    fill_rule: str = "evenodd",
) -> List[PathSegment]:
    """Generate hatch lines inside one compound filled shape.

    Multiple closed contours are scanned together so holes, such as the
    counter inside a letter O, remove hatch spans instead of becoming
    independently filled islands.

    Args:
        polygons: Ordered contour vertex lists for one filled shape.
        angle: Hatch angle in degrees (0 = horizontal).
        spacing: Distance between hatch lines in mm.
        alternate: If True, alternate directions for smoother travel.
        fill_rule: SVG fill rule, either ``evenodd`` or ``nonzero``.

    Returns:
        List of PathSegment instances representing hatch lines.
    """
    valid_polygons = [polygon for polygon in polygons if len(polygon) >= 3]
    if not valid_polygons or spacing <= 0:
        return []

    rad = math.radians(-angle)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    rotated_polygons = [
        [_rotate(pt, cos_a, sin_a) for pt in polygon]
        for polygon in valid_polygons
    ]
    rotated_points = [pt for polygon in rotated_polygons for pt in polygon]

    ys = [pt[1] for pt in rotated_points]
    y_min = min(ys)
    y_max = max(ys)

    edges = [
        edge
        for polygon in rotated_polygons
        for edge in _build_edges(polygon)
    ]

    segments: List[PathSegment] = []
    y = y_min + spacing
    line_idx = 0

    while y < y_max:
        pairs = _scanline_spans(edges, y, fill_rule)

        if alternate and line_idx % 2 == 1:
            pairs = list(reversed(pairs))

        for x_start, x_end in pairs:
            p1 = _unrotate(x_start, y, cos_a, sin_a)
            p2 = _unrotate(x_end, y, cos_a, sin_a)
            points = [Vector2d(*p1), Vector2d(*p2)]
            if alternate and line_idx % 2 == 1:
                points.reverse()
            segments.append(
                PathSegment(
                    points=points,
                    element_id="hatch",
                    element_type="hatch",
                    path_type=PathType.OPEN,
                )
            )

        y += spacing
        line_idx += 1

    return segments


# ------------------------------------------------------------------
# Internal geometry helpers
# ------------------------------------------------------------------


def _rotate(
    pt: Vector2d, cos_a: float, sin_a: float
) -> Tuple[float, float]:
    """Rotate a point around the origin.

    Args:
        pt: Point to rotate.
        cos_a: Precomputed cosine of the rotation angle.
        sin_a: Precomputed sine of the rotation angle.

    Returns:
        Rotated (x, y) tuple.
    """
    return (pt.x * cos_a - pt.y * sin_a, pt.x * sin_a + pt.y * cos_a)


def _unrotate(
    x: float, y: float, cos_a: float, sin_a: float
) -> Tuple[float, float]:
    """Reverse-rotate a point back to the original coordinate system.

    Args:
        x: X coordinate in rotated space.
        y: Y coordinate in rotated space.
        cos_a: Precomputed cosine of the rotation angle.
        sin_a: Precomputed sine of the rotation angle.

    Returns:
        Original (x, y) tuple.
    """
    return (x * cos_a + y * sin_a, -x * sin_a + y * cos_a)


def _build_edges(
    polygon: List[Tuple[float, float]],
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Build edge list from a polygon's vertices.

    Args:
        polygon: Ordered vertex list (rotated coordinates).

    Returns:
        List of (start, end) edge tuples.
    """
    return list(zip(polygon, polygon[1:] + polygon[:1]))


def _scanline_intersections(
    edges: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    y: float,
) -> List[float]:
    """Find X intersections of a horizontal scanline with polygon edges.

    Args:
        edges: Polygon edge list.
        y: Y coordinate of the scanline.

    Returns:
        List of X coordinates where scanline crosses edges.
    """
    intersections: List[float] = []
    for (x1, y1), (x2, y2) in edges:
        if y1 == y2:
            continue
        if (y1 <= y < y2) or (y2 <= y < y1):
            t = (y - y1) / (y2 - y1)
            x = x1 + t * (x2 - x1)
            intersections.append(x)
    return intersections


def _scanline_spans(
    edges: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    y: float,
    fill_rule: str,
) -> List[Tuple[float, float]]:
    """Return filled X spans for a scanline under the requested fill rule."""
    normalized = fill_rule.strip().lower().replace("-", "")
    if normalized == "nonzero":
        return _scanline_spans_nonzero(edges, y)
    return _scanline_spans_evenodd(edges, y)


def _scanline_spans_evenodd(
    edges: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    y: float,
) -> List[Tuple[float, float]]:
    """Pair intersections using SVG's even-odd fill rule."""
    intersections = _scanline_intersections(edges, y)
    intersections.sort()
    return [
        (x_start, x_end)
        for x_start, x_end in zip(intersections[::2], intersections[1::2])
        if x_end > x_start
    ]


def _scanline_spans_nonzero(
    edges: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    y: float,
) -> List[Tuple[float, float]]:
    """Build filled spans by accumulating winding crossings."""
    events: List[Tuple[float, int]] = []
    for (x1, y1), (x2, y2) in edges:
        if y1 == y2:
            continue
        if (y1 <= y < y2) or (y2 <= y < y1):
            t = (y - y1) / (y2 - y1)
            x = x1 + t * (x2 - x1)
            events.append((x, 1 if y2 > y1 else -1))

    events.sort(key=lambda event: event[0])

    spans: List[Tuple[float, float]] = []
    winding = 0
    span_start: Optional[float] = None
    idx = 0

    while idx < len(events):
        x = events[idx][0]
        delta = 0
        while idx < len(events) and events[idx][0] == x:
            delta += events[idx][1]
            idx += 1

        was_inside = winding != 0
        winding += delta
        is_inside = winding != 0

        if not was_inside and is_inside:
            span_start = x
        elif was_inside and not is_inside and span_start is not None:
            if x > span_start:
                spans.append((span_start, x))
            span_start = None

    return spans
