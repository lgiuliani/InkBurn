"""Vector hatching (fill) algorithm for InkBurn extension.

Generates parallel hatch lines inside a closed polygon, used by
fill-type laser jobs to engrave the interior of shapes.
"""

import math
from typing import List, Tuple

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
    if len(polygon) < 3 or spacing <= 0:
        return []

    rad = math.radians(-angle)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    rotated = [_rotate(pt, cos_a, sin_a) for pt in polygon]

    ys = [pt[1] for pt in rotated]
    y_min = min(ys)
    y_max = max(ys)

    edges = _build_edges(rotated)

    segments: List[PathSegment] = []
    y = y_min + spacing
    line_idx = 0

    while y < y_max:
        intersections = _scanline_intersections(edges, y)
        intersections.sort()

        pairs = list(zip(intersections[::2], intersections[1::2]))

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
    edges = []
    n = len(polygon)
    for i in range(n):
        edges.append((polygon[i], polygon[(i + 1) % n]))
    return edges


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
