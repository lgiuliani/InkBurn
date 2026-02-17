"""Tests for Job model JSON serialization and data-job-X SVG I/O."""

import json
import uuid

import pytest
from lxml import etree

# Allow imports from the extension root
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.job import Job, JobType, LaserMode
from models.layer import Layer


class TestJobSerialization:
    """Job JSON round-trip tests."""

    def test_default_cut_job_round_trip(self) -> None:
        """A default cut job survives JSON round-trip unchanged."""
        job = Job.create_default(JobType.CUT)
        raw = job.to_json()
        restored = Job.from_json(raw)
        assert restored.type == JobType.CUT
        assert restored.active is True
        assert restored.passes == 1
        assert restored.speed == 800.0
        assert restored.id == job.id

    def test_fill_job_params_preserved(self) -> None:
        """Fill job type-specific params survive serialization."""
        job = Job.create_default(JobType.FILL)
        job.params["angle"] = 90.0
        job.params["spacing"] = 0.2
        job.params["alternate"] = False

        restored = Job.from_json(job.to_json())
        assert restored.type == JobType.FILL
        assert restored.params["angle"] == 90.0
        assert restored.params["spacing"] == 0.2
        assert restored.params["alternate"] is False

    def test_raster_job_params_preserved(self) -> None:
        """Raster job type-specific params survive serialization."""
        job = Job.create_default(JobType.RASTER)
        job.params["dpi"] = 600
        job.params["direction"] = "vertical"

        restored = Job.from_json(job.to_json())
        assert restored.type == JobType.RASTER
        assert restored.params["dpi"] == 600
        assert restored.params["direction"] == "vertical"
        assert restored.laser_mode == LaserMode.M4

    def test_uuid_generation(self) -> None:
        """Each new job gets a unique UUID."""
        j1 = Job.create_default(JobType.CUT)
        j2 = Job.create_default(JobType.CUT)
        assert j1.id != j2.id
        uuid.UUID(j1.id)  # validates format

    def test_inactive_job(self) -> None:
        """Active flag serialization."""
        job = Job.create_default(JobType.CUT)
        job.active = False
        restored = Job.from_json(job.to_json())
        assert restored.active is False

    def test_power_values(self) -> None:
        """Custom power_min/power_max survive round-trip."""
        job = Job(power_min=100.0, power_max=900.0)
        restored = Job.from_json(job.to_json())
        assert restored.power_min == 100.0
        assert restored.power_max == 900.0


class TestLayerSvgIO:
    """Layer data-job-X SVG attribute tests."""

    def _make_layer_elem(self, layer_id: str, jobs: list[Job]) -> etree._Element:
        """Create a mock SVG layer element with data-job-X attributes."""
        layer = Layer(layer_id=layer_id, label="Test Layer", jobs=jobs)
        elem = etree.Element("g", id=layer_id)
        for key, val in layer.to_svg_attributes().items():
            elem.set(key, val)
        return elem

    def test_empty_layer(self) -> None:
        """Layer with no jobs produces no data-job-X attributes."""
        layer = Layer(layer_id="L1", label="Empty")
        attrs = layer.to_svg_attributes()
        assert len(attrs) == 0

    def test_single_job_round_trip(self) -> None:
        """Single job persists and restores from SVG attributes."""
        job = Job.create_default(JobType.CUT)
        job.speed = 1200.0
        elem = self._make_layer_elem("layer1", [job])

        restored = Layer.from_svg_attributes(
            "layer1", "Test", True, dict(elem.attrib)
        )
        assert len(restored.jobs) == 1
        assert restored.jobs[0].speed == 1200.0
        assert restored.jobs[0].type == JobType.CUT

    def test_multiple_jobs_order_preserved(self) -> None:
        """Multiple jobs maintain their order through serialization."""
        j0 = Job.create_default(JobType.CUT)
        j1 = Job.create_default(JobType.FILL)
        j2 = Job.create_default(JobType.RASTER)
        elem = self._make_layer_elem("layer1", [j0, j1, j2])

        restored = Layer.from_svg_attributes(
            "layer1", "Test", True, dict(elem.attrib)
        )
        assert len(restored.jobs) == 3
        assert restored.jobs[0].type == JobType.CUT
        assert restored.jobs[1].type == JobType.FILL
        assert restored.jobs[2].type == JobType.RASTER

    def test_job_attributes_unchanged_after_save(self) -> None:
        """Job params stored in SVG appear unchanged after re-reading."""
        job = Job.create_default(JobType.FILL)
        job.params["angle"] = 135.0
        job.params["spacing"] = 0.3

        elem = self._make_layer_elem("L1", [job])
        raw_attr = elem.get("data-job-0")
        assert raw_attr is not None

        parsed = json.loads(raw_attr)
        assert parsed["params"]["angle"] == 135.0
        assert parsed["params"]["spacing"] == 0.3

    def test_active_jobs_filter(self) -> None:
        """Layer.active_jobs() respects active flag."""
        j0 = Job.create_default(JobType.CUT)
        j0.active = False
        j1 = Job.create_default(JobType.FILL)
        j1.active = True

        layer = Layer(layer_id="L1", label="Test", jobs=[j0, j1])
        active = layer.active_jobs()
        assert len(active) == 1
        assert active[0].type == JobType.FILL


class TestLayerJobManagement:
    """Layer job add/remove/reorder operations."""

    def test_add_job(self) -> None:
        """Adding a job increases the list length."""
        layer = Layer(layer_id="L1", label="Test")
        assert len(layer.jobs) == 0
        layer.add_job(JobType.CUT)
        assert len(layer.jobs) == 1

    def test_remove_job(self) -> None:
        """Removing a job decreases the list length."""
        layer = Layer(layer_id="L1", label="Test")
        layer.add_job(JobType.CUT)
        layer.add_job(JobType.FILL)
        layer.remove_job(0)
        assert len(layer.jobs) == 1
        assert layer.jobs[0].type == JobType.FILL

    def test_move_job_up(self) -> None:
        """Moving a job up swaps it with the previous one."""
        layer = Layer(layer_id="L1", label="Test")
        j0 = layer.add_job(JobType.CUT)
        j1 = layer.add_job(JobType.FILL)
        assert layer.move_job_up(1)
        assert layer.jobs[0].id == j1.id
        assert layer.jobs[1].id == j0.id

    def test_move_job_down(self) -> None:
        """Moving a job down swaps it with the next one."""
        layer = Layer(layer_id="L1", label="Test")
        j0 = layer.add_job(JobType.CUT)
        j1 = layer.add_job(JobType.FILL)
        assert layer.move_job_down(0)
        assert layer.jobs[0].id == j1.id
        assert layer.jobs[1].id == j0.id

    def test_move_job_up_at_top(self) -> None:
        """Moving the first job up returns False."""
        layer = Layer(layer_id="L1", label="Test")
        layer.add_job(JobType.CUT)
        assert not layer.move_job_up(0)

    def test_move_job_down_at_bottom(self) -> None:
        """Moving the last job down returns False."""
        layer = Layer(layer_id="L1", label="Test")
        layer.add_job(JobType.CUT)
        assert not layer.move_job_down(0)
