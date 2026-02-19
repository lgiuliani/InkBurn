"""Path-related data models for InkBurn extension.

Contains geometry primitives and G-code generation state used by the
path extractor, optimizer, and code generator.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from inkex.transforms import Vector2d


class PathType(Enum):
    """Whether a path segment forms a closed loop or is open."""

    CLOSED = "closed"
    OPEN = "open"


def distance(p1: Vector2d, p2: Vector2d) -> float:
    """Calculate Euclidean distance between two points.

    Args:
        p1: First point.
        p2: Second point.

    Returns:
        Distance between points.
    """
    return math.hypot(p2.x - p1.x, p2.y - p1.y)


@dataclass
class PathSegment:
    """Represents a continuous path segment with metadata.

    Attributes:
        points: Ordered list of 2-D vertices.
        element_id: SVG element ``id`` this segment was extracted from.
        element_type: SVG tag name (e.g. ``path``, ``rect``).
        path_type: Whether the segment is closed or open.
    """

    points: List[Vector2d]
    element_id: str
    element_type: str
    path_type: PathType = PathType.OPEN

    _length: float = field(default=-1.0, init=False, repr=False, compare=False)

    @property
    def start_point(self) -> Vector2d:
        """Get the starting point of the segment."""
        return self.points[0] if self.points else Vector2d(0, 0)

    @property
    def end_point(self) -> Vector2d:
        """Get the ending point of the segment."""
        return self.points[-1] if self.points else Vector2d(0, 0)

    @property
    def length(self) -> float:
        """Calculate total length of the segment."""
        if self._length < 0:
            if len(self.points) < 2:
                self._length = 0.0
            else:
            self._length = sum(
                distance(a, b) for a, b in zip(self.points, self.points[1:])
            )
        return self._length

    def reverse(self) -> "PathSegment":
        """Return a reversed copy of this segment."""
        return PathSegment(
            points=list(reversed(self.points)),
            element_id=self.element_id,
            element_type=self.element_type,
            path_type=self.path_type,
        )

    def is_closed(self) -> bool:
        """Check if path forms a closed loop."""
        if len(self.points) < 3:
            return False
        return distance(self.start_point, self.end_point) < 0.01


@dataclass
class GCodeState:
    """Tracks the current state of G-code generation to avoid redundancy.

    Attributes:
        x: Last emitted X coordinate.
        y: Last emitted Y coordinate.
        command: Last emitted G command (``G0`` or ``G1``).
        power: Last emitted S value.
        speed: Last emitted F value.
    """

    x: Optional[float] = None
    y: Optional[float] = None
    command: Optional[str] = None
    power: Optional[int] = None
    speed: Optional[int] = None

    def reset(self) -> None:
        """Reset all state values."""
        self.x = None
        self.y = None
        self.command = None
        self.power = None
        self.speed = None


@dataclass
class OptimizationMetrics:
    """Metrics collected during path optimization.

    Attributes:
        original_travel_distance: Travel distance before optimization.
        optimized_travel_distance: Travel distance after optimization.
        original_engrave_distance: Engrave distance before optimization.
        optimized_engrave_distance: Engrave distance after optimization.
        paths_reversed: Number of segments reversed for shorter travel.
    """

    original_travel_distance: float = 0.0
    optimized_travel_distance: float = 0.0
    original_engrave_distance: float = 0.0
    optimized_engrave_distance: float = 0.0
    paths_reversed: int = 0

    @property
    def travel_savings(self) -> float:
        """Calculate travel distance savings percentage."""
        if self.original_travel_distance == 0:
            return 0.0
        return (
            (self.original_travel_distance - self.optimized_travel_distance)
            / self.original_travel_distance
            * 100
        )
