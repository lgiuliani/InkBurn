"""Path optimization algorithms for reducing travel distance.

Uses a greedy nearest-neighbor heuristic to reorder path segments
and optionally reverse open paths when it reduces travel.
"""

import logging
from typing import List, Tuple

from inkex.transforms import Vector2d

from models.path import OptimizationMetrics, PathSegment, PathType, distance

logger = logging.getLogger(__name__)


class PathOptimizer:
    """Optimizes path order and direction to minimize travel distance.

    Attributes:
        start_position: Starting laser position for the optimization.
    """

    def __init__(self, start_position: Vector2d = Vector2d(0, 0)) -> None:
        """Initialize path optimizer.

        Args:
            start_position: Starting position for optimization.
        """
        self.start_position = start_position

    def optimize(
        self,
        segments: List[PathSegment],
        enable_direction_optimization: bool = True,
    ) -> Tuple[List[PathSegment], OptimizationMetrics]:
        """Optimize path order using greedy nearest-neighbor algorithm.

        Args:
            segments: Path segments to optimize.
            enable_direction_optimization: Whether to reverse paths when beneficial.

        Returns:
            Tuple of (optimized segments, metrics).
        """
        if not segments:
            return [], OptimizationMetrics()

        metrics = OptimizationMetrics()
        metrics.original_engrave_distance = sum(s.length for s in segments)
        metrics.original_travel_distance = self._travel_distance(
            segments, self.start_position
        )

        optimized: List[PathSegment] = []
        remaining = segments.copy()
        current_pos = self.start_position

        while remaining:
            nearest_idx, should_reverse, _ = self._find_nearest(
                current_pos, remaining, enable_direction_optimization
            )

            segment = remaining.pop(nearest_idx)
            if should_reverse and enable_direction_optimization:
                segment = segment.reverse()
                metrics.paths_reversed += 1

            optimized.append(segment)
            current_pos = segment.end_point

        metrics.optimized_engrave_distance = sum(s.length for s in optimized)
        metrics.optimized_travel_distance = self._travel_distance(
            optimized, self.start_position
        )

        return optimized, metrics

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_nearest(
        self,
        current_pos: Vector2d,
        segments: List[PathSegment],
        check_reverse: bool,
    ) -> Tuple[int, bool, float]:
        """Find the nearest segment to the current position.

        Args:
            current_pos: Current laser position.
            segments: Available segments.
            check_reverse: Whether to consider reversing paths.

        Returns:
            Tuple of (segment index, should reverse, distance).
        """
        best_idx = 0
        best_reverse = False
        best_dist = float("inf")

        for idx, seg in enumerate(segments):
            dist_start = distance(current_pos, seg.start_point)
            if dist_start < best_dist:
                best_dist = dist_start
                best_idx = idx
                best_reverse = False

            if check_reverse and seg.path_type != PathType.CLOSED:
                dist_end = distance(current_pos, seg.end_point)
                if dist_end < best_dist:
                    best_dist = dist_end
                    best_idx = idx
                    best_reverse = True

        return best_idx, best_reverse, best_dist

    def _travel_distance(
        self,
        segments: List[PathSegment],
        start_pos: Vector2d,
    ) -> float:
        """Calculate total travel distance for a segment sequence.

        Args:
            segments: Ordered list of segments.
            start_pos: Starting position.

        Returns:
            Total travel distance.
        """
        if not segments:
            return 0.0

        total = distance(start_pos, segments[0].start_point)
        for i in range(len(segments) - 1):
            total += distance(segments[i].end_point, segments[i + 1].start_point)
        return total
        
