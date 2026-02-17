"""Tests for geometry modules: hatching and path models."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from inkex.transforms import Vector2d

from geometry.hatching import generate_hatch_lines
from models.path import PathSegment, PathType, distance, OptimizationMetrics


class TestDistance:
    """Euclidean distance function tests."""

    def test_zero_distance(self) -> None:
        """Same point returns zero."""
        p = Vector2d(5, 5)
        assert distance(p, p) == pytest.approx(0.0)

    def test_horizontal(self) -> None:
        """Horizontal distance calculation."""
        assert distance(Vector2d(0, 0), Vector2d(3, 0)) == pytest.approx(3.0)

    def test_diagonal(self) -> None:
        """3-4-5 triangle."""
        assert distance(Vector2d(0, 0), Vector2d(3, 4)) == pytest.approx(5.0)


class TestPathSegment:
    """PathSegment property and method tests."""

    def _make_segment(self, points: list[tuple[float, float]]) -> PathSegment:
        """Helper to create a segment from tuples."""
        return PathSegment(
            points=[Vector2d(*p) for p in points],
            element_id="test",
            element_type="path",
        )

    def test_start_end_points(self) -> None:
        """Start and end point accessors."""
        seg = self._make_segment([(0, 0), (5, 5), (10, 0)])
        assert seg.start_point.x == 0
        assert seg.end_point.x == 10

    def test_length(self) -> None:
        """Length of a straight horizontal line."""
        seg = self._make_segment([(0, 0), (10, 0)])
        assert seg.length == pytest.approx(10.0)

    def test_reverse(self) -> None:
        """Reversing a segment reverses point order."""
        seg = self._make_segment([(0, 0), (5, 5), (10, 0)])
        rev = seg.reverse()
        assert rev.start_point.x == 10
        assert rev.end_point.x == 0
        assert rev.element_id == seg.element_id

    def test_is_closed(self) -> None:
        """Segment with start ≈ end is closed."""
        seg = self._make_segment([(0, 0), (10, 0), (10, 10), (0, 0.005)])
        assert seg.is_closed()

    def test_is_open(self) -> None:
        """Segment with start ≠ end is open."""
        seg = self._make_segment([(0, 0), (10, 0), (10, 10)])
        assert not seg.is_closed()


class TestOptimizationMetrics:
    """Optimization metrics calculations."""

    def test_travel_savings(self) -> None:
        """Savings percentage calculation."""
        m = OptimizationMetrics(
            original_travel_distance=100.0,
            optimized_travel_distance=60.0,
        )
        assert m.travel_savings == pytest.approx(40.0)

    def test_zero_original(self) -> None:
        """Zero original distance returns 0% savings."""
        m = OptimizationMetrics()
        assert m.travel_savings == pytest.approx(0.0)


class TestHatching:
    """Vector hatching algorithm tests."""

    def _square(self) -> list[Vector2d]:
        """10x10 square polygon."""
        return [
            Vector2d(0, 0),
            Vector2d(10, 0),
            Vector2d(10, 10),
            Vector2d(0, 10),
        ]

    def test_horizontal_hatching(self) -> None:
        """Horizontal hatch lines are generated inside a square."""
        lines = generate_hatch_lines(
            self._square(), angle=0, spacing=1.0, alternate=False
        )
        assert len(lines) > 0
        for seg in lines:
            assert len(seg.points) == 2
            assert seg.path_type == PathType.OPEN

    def test_spacing_controls_count(self) -> None:
        """Smaller spacing produces more hatch lines."""
        fine = generate_hatch_lines(
            self._square(), angle=0, spacing=0.5, alternate=False
        )
        coarse = generate_hatch_lines(
            self._square(), angle=0, spacing=2.0, alternate=False
        )
        assert len(fine) > len(coarse)

    def test_angled_hatching(self) -> None:
        """45-degree hatch lines are generated."""
        lines = generate_hatch_lines(
            self._square(), angle=45, spacing=1.0, alternate=True
        )
        assert len(lines) > 0

    def test_empty_polygon(self) -> None:
        """Empty polygon produces no hatch lines."""
        assert generate_hatch_lines([], spacing=1.0) == []

    def test_zero_spacing(self) -> None:
        """Zero spacing produces no hatch lines."""
        assert generate_hatch_lines(self._square(), spacing=0) == []
