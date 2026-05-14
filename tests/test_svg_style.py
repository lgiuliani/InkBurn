"""Tests for SVG style and paint helpers."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from inkex.transforms import Vector2d
from lxml import etree

from models.job import Job, JobType
from svg_style import fill_power


class TestFillPowerColorMapping:
    """Fill color to laser power mapping."""

    def _element_with_fill(self, fill: str) -> etree._Element:
        """Create a minimal element with a fill style."""
        elem = etree.Element("path")
        elem.set("style", f"fill:{fill}")
        return elem

    def test_black_fill_uses_power_max(self) -> None:
        """Black fill maps to maximum power."""
        job = Job.create_default(JobType.FILL)
        job.power_min = 100.0
        job.power_max = 900.0
        assert fill_power(
            self._element_with_fill("#000000"), job
        ) == pytest.approx(900.0)

    def test_white_fill_uses_power_min(self) -> None:
        """White fill maps to minimum power."""
        job = Job.create_default(JobType.FILL)
        job.power_min = 100.0
        job.power_max = 900.0
        assert fill_power(
            self._element_with_fill("#ffffff"), job
        ) == pytest.approx(100.0)

    def test_mid_fill_uses_intermediate_power(self) -> None:
        """Intermediate luminance maps inside the power range."""
        job = Job.create_default(JobType.FILL)
        job.power_min = 100.0
        job.power_max = 900.0
        power = fill_power(self._element_with_fill("rgb(128,128,128)"), job)
        assert 100.0 < power < 900.0

    def test_named_fill_is_calculated_by_parser(self) -> None:
        """Named CSS colors are parsed without a local lookup table."""
        job = Job.create_default(JobType.FILL)
        job.power_min = 0.0
        job.power_max = 1000.0
        power = fill_power(self._element_with_fill("white"), job)
        assert power == pytest.approx(0.0)

    def test_linear_gradient_samples_at_point(self) -> None:
        """Gradient fill power depends on the hatch point location."""
        job = Job.create_default(JobType.FILL)
        job.power_min = 100.0
        job.power_max = 900.0

        svg = etree.Element("svg")
        gradient = etree.SubElement(svg, "linearGradient", id="grad")
        etree.SubElement(
            gradient,
            "stop",
            offset="0%",
            style="stop-color:#000000",
        )
        etree.SubElement(
            gradient,
            "stop",
            offset="100%",
            style="stop-color:#ffffff",
        )
        shape = etree.SubElement(svg, "path")
        shape.set("style", "fill:url(#grad)")

        bbox = (0.0, 0.0, 10.0, 10.0)
        dark_power = fill_power(shape, job, Vector2d(0, 10), 10.0, bbox)
        light_power = fill_power(shape, job, Vector2d(10, 10), 10.0, bbox)
        mid_power = fill_power(shape, job, Vector2d(5, 10), 10.0, bbox)

        assert dark_power == pytest.approx(900.0)
        assert light_power == pytest.approx(100.0)
        assert 100.0 < mid_power < 900.0
