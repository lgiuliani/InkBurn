"""Job data model for InkBurn extension.

A Job represents a single laser operation (cut, fill, or raster) on a layer.
Jobs are serialized as JSON and stored in ``data-job-X`` attributes on the
SVG layer ``<g>`` element.
"""

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Tuple, Type

StorageKind = Literal["job", "params"]

# GTK / schema row: (name, label, type, min, max, step) — matches ``ParamDef`` in config_core.
JobParamSchemaRow = Tuple[str, str, Type[Any], float, float, float]


class JobType(str, Enum):
    """Laser job type."""

    CUT = "cut"
    FILL = "fill"
    RASTER = "raster"


class LaserMode(str, Enum):
    """GRBL laser enable command."""

    M3 = "M3"
    M4 = "M4"


@dataclass(frozen=True, slots=True)
class JobParamSpec:
    """Single configurable job field: UI metadata and optional ``params`` default."""

    name: str
    label: str
    value_type: Type[Any]
    min_v: float
    max_v: float
    step: float
    storage: StorageKind = "job"
    default: Any = None


def _job_param_specs() -> Dict[JobType, Tuple[JobParamSpec, ...]]:
    """Authoritative job parameter list per type (order = UI order)."""
    return {
        JobType.CUT: (
            JobParamSpec("speed", "Feed rate (mm/min)", float, 10, 10000, 10),
            JobParamSpec("power_max", "Power max (S value)", float, 0, 10000, 10),
            JobParamSpec("power_min", "Power min (S value)", float, 0, 10000, 10),
            JobParamSpec("passes", "Passes", int, 1, 100, 1),
            JobParamSpec("offset", "Offset (mm)", float, -10, 10, 0.01),
        ),
        JobType.FILL: (
            JobParamSpec("speed", "Feed rate (mm/min)", float, 10, 10000, 10),
            JobParamSpec("power_max", "Power max (S value)", float, 0, 10000, 10),
            JobParamSpec("power_min", "Power min (S value)", float, 0, 10000, 10),
            JobParamSpec("passes", "Passes", int, 1, 100, 1),
            JobParamSpec(
                "angle",
                "Hatch angle (°)",
                float,
                0,
                360,
                1,
                "params",
                45.0,
            ),
            JobParamSpec(
                "spacing",
                "Line spacing (mm)",
                float,
                0.01,
                10.0,
                0.01,
                "params",
                0.5,
            ),
            JobParamSpec(
                "alternate",
                "Alternate direction",
                bool,
                0,
                1,
                1,
                "params",
                True,
            ),
        ),
        JobType.RASTER: (
            JobParamSpec("speed", "Feed rate (mm/min)", float, 10, 10000, 10),
            JobParamSpec("power_max", "Power max (S value)", float, 0, 10000, 10),
            JobParamSpec("power_min", "Power min (S value)", float, 0, 10000, 10),
            JobParamSpec(
                "dpi",
                "Resolution (DPI)",
                int,
                50,
                1200,
                10,
                "params",
                300,
            ),
            JobParamSpec(
                "direction",
                "Direction",
                str,
                0,
                0,
                0,
                "params",
                "horizontal",
            ),
        ),
    }


JOB_PARAM_SPECS: Dict[JobType, Tuple[JobParamSpec, ...]] = _job_param_specs()


def job_param_schema_rows() -> Dict[JobType, List[JobParamSchemaRow]]:
    """Schema tuples for the layer/job GTK dialog (``PARAM_SCHEMA``)."""
    return {
        jt: [
            (s.name, s.label, s.value_type, s.min_v, s.max_v, s.step)
            for s in JOB_PARAM_SPECS[jt]
        ]
        for jt in JobType
    }


def _default_params_for_type(job_type: JobType) -> Dict[str, Any]:
    """Type-specific ``params`` dict defaults (subset of ``JOB_PARAM_SPECS``)."""
    return {
        s.name: s.default
        for s in JOB_PARAM_SPECS[job_type]
        if s.storage == "params"
    }


@dataclass(slots=True)
class Job:
    """Single laser operation on a layer.

    Attributes:
        id: Unique identifier (UUID string).
        type: One of cut / fill / raster.
        active: Whether this job participates in export.
        passes: Number of repeated passes.
        speed: Feed rate in mm/min.
        power_min: Minimum laser power (S value).
        power_max: Maximum laser power (S value).
        air_assist: Whether air assist is enabled.
        offset: Contour offset in mm (positive = outward).
        laser_mode: GRBL laser command (M3 or M4).
        params: Type-specific extra parameters.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: JobType = JobType.CUT
    active: bool = True
    passes: int = 1
    speed: float = 800.0
    power_min: float = 0.0
    power_max: float = 600.0
    air_assist: bool = True
    offset: float = 0.0
    laser_mode: LaserMode = LaserMode.M3
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize job to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "active": self.active,
            "passes": self.passes,
            "speed": self.speed,
            "power_min": self.power_min,
            "power_max": self.power_max,
            "air_assist": self.air_assist,
            "offset": self.offset,
            "laser_mode": self.laser_mode.value,
            "params": dict(self.params),
        }

    def to_json(self) -> str:
        """Serialize job to a JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Deserialize a job from a dictionary.

        Args:
            data: Dictionary with job fields.

        Returns:
            Populated Job instance.
        """
        job_type = JobType(data.get("type", "cut"))
        default_params = _default_params_for_type(job_type).copy()
        raw_params = data.get("params", {})
        default_params.update(raw_params)

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=job_type,
            active=bool(data.get("active", True)),
            passes=int(data.get("passes", 1)),
            speed=float(data.get("speed", 800.0)),
            power_min=float(data.get("power_min", 0.0)),
            power_max=float(data.get("power_max", 600.0)),
            air_assist=bool(data.get("air_assist", True)),
            offset=float(data.get("offset", 0.0)),
            laser_mode=LaserMode(data.get("laser_mode", "M3")),
            params=default_params,
        )

    @classmethod
    def from_json(cls, raw: str) -> "Job":
        """Deserialize a job from a JSON string.

        Args:
            raw: JSON string.

        Returns:
            Populated Job instance.
        """
        return cls.from_dict(json.loads(raw))

    @classmethod
    def create_default(cls, job_type: JobType) -> "Job":
        """Create a new job with sensible defaults for the given type.

        Args:
            job_type: Type of job to create.

        Returns:
            New Job instance with default parameters.
        """
        params = _default_params_for_type(job_type).copy()
        laser_mode = LaserMode.M4 if job_type == JobType.RASTER else LaserMode.M3
        return cls(type=job_type, laser_mode=laser_mode, params=params)

    def get_summary(self) -> str:
        """Return a short human-readable summary of the job."""
        mode = self.laser_mode.value
        active = "✓" if self.active else "✗"
        if self.type == JobType.CUT:
            return (
                f"[{active}] Cut: S{self.power_max:.0f} "
                f"F{self.speed:.0f} {self.passes}× {mode}"
            )
        if self.type == JobType.FILL:
            fb = _default_params_for_type(JobType.FILL)
            angle = self.params.get("angle", fb["angle"])
            spacing = self.params.get("spacing", fb["spacing"])
            return (
                f"[{active}] Fill: S{self.power_min:.0f}-{self.power_max:.0f} "
                f"{spacing}mm {angle:.0f}° {mode}"
            )
        if self.type == JobType.RASTER:
            fb = _default_params_for_type(JobType.RASTER)
            dpi = self.params.get("dpi", fb["dpi"])
            direction = self.params.get("direction", fb["direction"])
            return (
                f"[{active}] Raster: {dpi}DPI "
                f"S{self.power_min:.0f}-{self.power_max:.0f} {direction} {mode}"
            )
        return f"[{active}] Unknown job type"
