"""Layer data model for InkBurn extension.

A Layer groups zero or more Jobs and maps 1:1 to an Inkscape SVG layer
(a ``<g>`` element with ``inkscape:groupmode="layer"``).
"""

from dataclasses import dataclass, field
from typing import Dict, List

from models.job import Job, JobType


@dataclass
class Layer:
    """Represents an SVG layer with its associated laser jobs.

    Attributes:
        layer_id: SVG element id of the layer ``<g>``.
        label: Human-readable layer name (``inkscape:label``).
        visible: Whether the layer is currently visible in Inkscape.
        jobs: Ordered list of jobs for this layer.
    """

    layer_id: str
    label: str
    visible: bool = True
    jobs: List[Job] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def add_job(self, job_type: JobType = JobType.CUT) -> Job:
        """Create and append a new default job.

        Args:
            job_type: Type of job to create.

        Returns:
            The newly created job.
        """
        job = Job.create_default(job_type)
        self.jobs.append(job)
        return job

    def remove_job(self, index: int) -> None:
        """Remove the job at the given index.

        Args:
            index: Zero-based position in the job list.
        """
        if 0 <= index < len(self.jobs):
            self.jobs.pop(index)

    def move_job_up(self, index: int) -> bool:
        """Swap the job at *index* with the one above it.

        Args:
            index: Zero-based position.

        Returns:
            True if the move succeeded.
        """
        if index > 0:
            self.jobs[index], self.jobs[index - 1] = (
                self.jobs[index - 1],
                self.jobs[index],
            )
            return True
        return False

    def move_job_down(self, index: int) -> bool:
        """Swap the job at *index* with the one below it.

        Args:
            index: Zero-based position.

        Returns:
            True if the move succeeded.
        """
        if index < len(self.jobs) - 1:
            self.jobs[index], self.jobs[index + 1] = (
                self.jobs[index + 1],
                self.jobs[index],
            )
            return True
        return False

    def active_jobs(self) -> List[Job]:
        """Return only the active jobs, preserving order."""
        return [j for j in self.jobs if j.active]

    # ------------------------------------------------------------------
    # SVG attribute I/O
    # ------------------------------------------------------------------

    def to_svg_attributes(self) -> Dict[str, str]:
        """Serialize all jobs to ``data-job-X`` attribute pairs.

        Returns:
            Dict ready to be set on the SVG ``<g>`` element.
        """
        attrs: Dict[str, str] = {}
        for idx, job in enumerate(self.jobs):
            attrs[f"data-job-{idx}"] = job.to_json()
        return attrs

    @classmethod
    def from_svg_attributes(
        cls,
        layer_id: str,
        label: str,
        visible: bool,
        attrs: Dict[str, str],
    ) -> "Layer":
        """Build a Layer by reading ``data-job-X`` attributes.

        Args:
            layer_id: SVG element id.
            label: Human-readable name.
            visible: Layer visibility state.
            attrs: Full attribute dict from the ``<g>`` element.

        Returns:
            Populated Layer instance.
        """
        jobs: List[Job] = []
        idx = 0
        while True:
            key = f"data-job-{idx}"
            raw = attrs.get(key)
            if raw is None:
                break
            jobs.append(Job.from_json(raw))
            idx += 1
        return cls(layer_id=layer_id, label=label, visible=visible, jobs=jobs)

    def get_summary(self) -> str:
        """Return a short human-readable summary of the layer."""
        if not self.jobs:
            return "No jobs"
        active = sum(1 for j in self.jobs if j.active)
        return f"{len(self.jobs)} job(s), {active} active"
