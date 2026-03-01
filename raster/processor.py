#!raster/processor.py
"""Raster image processing for InkBurn extension.

Converts embedded SVG ``<image>`` elements to scan-line G-code by:
1. Decoding the image data (base64 or file reference).
2. Converting to grayscale via PIL.
3. Resampling at the requested DPI.
4. Producing scan lines where pixel intensity maps linearly to laser
   power (white → power_min, black → power_max).
"""

import base64
import io
import logging
from typing import List, Optional, Tuple

from inkex.transforms import Transform, Vector2d
from lxml import etree

from models.job import Job
from models.path import PathSegment, PathType

logger = logging.getLogger(__name__)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment, misc]
    logger.warning("Pillow (PIL) not available — raster jobs will be skipped")


class RasterProcessor:
    """Processes ``<image>`` SVG elements into scan-line path segments.

    Each scan line contains per-pixel power values derived from the image
    grayscale.  The caller (G-code generator) is responsible for emitting
    the appropriate S values and must clamp them through MachineSettings
    before passing to the generator.

    Attributes:
        dpi: Output resolution in dots per inch.
        direction: Scan direction — ``"horizontal"`` or ``"vertical"``.
    """

    def __init__(self, dpi: int = 300, direction: str = "horizontal") -> None:
        """Initialize raster processor.

        Args:
            dpi: Scan resolution.
            direction: ``"horizontal"`` or ``"vertical"``.
        """
        self.dpi = max(1, dpi)
        self.direction = direction

    def process_image_element(
        self,
        element: etree._Element,
        viewbox_height: float,
        job: Job,
    ) -> List[Tuple[PathSegment, List[int]]]:
        """Convert an ``<image>`` element to scan-line segments with per-pixel power.

        Args:
            element: SVG ``<image>`` element.
            viewbox_height: SVG viewbox height for Y-axis flip.
            job: Job supplying ``power_min`` / ``power_max``.

        Returns:
            List of ``(PathSegment, power_list)`` tuples.  Each segment
            is one scan line; the corresponding ``power_list`` holds one
            integer S value per point.
        """
        if Image is None:
            logger.error("Pillow not installed — cannot process raster job")
            return []

        img = self._decode_image(element)
        if img is None:
            return []

        x_offset = float(element.get("x", "0"))
        y_offset = float(element.get("y", "0"))
        img_width = float(element.get("width", str(img.width)))
        img_height = float(element.get("height", str(img.height)))

        transform = Transform(element.composed_transform())

        mm_per_dot = 25.4 / self.dpi
        cols = max(1, int(img_width / mm_per_dot))
        rows = max(1, int(img_height / mm_per_dot))

        gray = img.convert("L").resize((cols, rows), Image.LANCZOS)
        pixels = gray.load()

        return self._scan_lines(
            pixels=pixels,
            cols=cols,
            rows=rows,
            mm_per_dot=mm_per_dot,
            x_offset=x_offset,
            y_offset=y_offset,
            viewbox_height=viewbox_height,
            transform=transform,
            power_min=job.power_min,
            power_range=job.power_max - job.power_min,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _decode_image(
        self, element: etree._Element
    ) -> "Optional[Image.Image]":
        """Decode an ``<image>`` element's href to a PIL Image.

        Args:
            element: SVG ``<image>`` element.

        Returns:
            PIL Image instance, or ``None`` on failure.
        """
        href = (
            element.get("{http://www.w3.org/1999/xlink}href")
            or element.get("href")
            or ""
        )
        if href.startswith("data:"):
            try:
                _header, data = href.split(",", 1)
                return Image.open(io.BytesIO(base64.b64decode(data)))
            except Exception:
                logger.error("Failed to decode inline image data")
                return None
        if href:
            try:
                return Image.open(href)
            except Exception:
                logger.error("Failed to open image file: %s", href)
                return None
        return None

    def _pixel_to_power(
        self, pixel_value: int, power_min: float, power_range: float
    ) -> int:
        """Map a grayscale pixel value to laser power.

        White (255) → ``power_min``, Black (0) → ``power_min + power_range``.

        Args:
            pixel_value: Grayscale intensity 0–255.
            power_min: Minimum power S value.
            power_range: ``power_max`` minus ``power_min``.

        Returns:
            Computed integer S value.
        """
        return int(power_min + (1.0 - pixel_value / 255.0) * power_range)

    def _scan_lines(
        self,
        pixels: object,
        cols: int,
        rows: int,
        mm_per_dot: float,
        x_offset: float,
        y_offset: float,
        viewbox_height: float,
        transform: Transform,
        power_min: float,
        power_range: float,
    ) -> List[Tuple[PathSegment, List[int]]]:
        """Generate scan-line segments in the configured direction.

        Horizontal mode iterates over rows as the outer loop; vertical
        mode iterates over columns.  The inner loop alternates direction
        (boustrophedon) to minimise travel between lines.

        Args:
            pixels: PIL pixel-access object (``image.load()``).
            cols: Number of pixel columns.
            rows: Number of pixel rows.
            mm_per_dot: Physical size of one pixel in mm.
            x_offset: Image X position in SVG user units.
            y_offset: Image Y position in SVG user units.
            viewbox_height: SVG viewbox height for Y-axis flip.
            transform: Composed element transform.
            power_min: Minimum laser power.
            power_range: ``power_max`` minus ``power_min``.

        Returns:
            List of ``(PathSegment, power_list)`` tuples.
        """
        is_horizontal = (self.direction == "horizontal")
        outer_count = rows if is_horizontal else cols
        inner_count = cols if is_horizontal else rows

        results: List[Tuple[PathSegment, List[int]]] = []

        for outer in range(outer_count):
            reversed_pass = (outer % 2 != 0)
            pixel_indices = (
                list(reversed(range(inner_count)))
                if reversed_pass
                else list(range(inner_count))
            )

            points: List[Vector2d] = []
            powers: List[int] = []

            for step, inner in enumerate(pixel_indices):
                col = inner if is_horizontal else outer
                row = outer if is_horizontal else inner

                if step == 0:
                    # Leading edge before the first pixel (rapid target).
                    # Forward → left edge of pixel 0.
                    # Reverse → right edge of pixel n-1.
                    sx, sy = self._pixel_edge(
                        col, row, mm_per_dot, x_offset, y_offset,
                        is_horizontal, entering=True, reversed_pass=reversed_pass,
                    )
                    tx, ty = transform.apply_to_point((sx, sy))
                    points.append(Vector2d(tx, viewbox_height - ty))
                    powers.append(0)

                # Trailing edge of this pixel (G1 destination).
                # Forward → right edge of pixel.
                # Reverse → left edge of pixel.
                sx, sy = self._pixel_edge(
                    col, row, mm_per_dot, x_offset, y_offset,
                    is_horizontal, entering=False, reversed_pass=reversed_pass,
                )
                tx, ty = transform.apply_to_point((sx, sy))
                points.append(Vector2d(tx, viewbox_height - ty))
                powers.append(
                    self._pixel_to_power(pixels[col, row], power_min, power_range)
                )

            if len(points) >= 2 and max(powers) > int(power_min):
                results.append((
                    PathSegment(
                        points=points,
                        element_id="raster",
                        element_type="raster",
                        path_type=PathType.OPEN,
                    ),
                    powers,
                ))

        return results

    @staticmethod
    def _pixel_edge(
        col: int,
        row: int,
        mm_per_dot: float,
        x_offset: float,
        y_offset: float,
        is_horizontal: bool,
        entering: bool,
        reversed_pass: bool,
    ) -> Tuple[float, float]:
        """Return the physical coordinate of a pixel edge.

        For the scan axis (X in horizontal, Y in vertical):
        - ``entering=True``  → the edge the beam enters from.
        - ``entering=False`` → the edge the beam exits toward.

        Forward pass enters from the left/top edge, exits right/bottom.
        Reversed pass enters from the right/bottom edge, exits left/top.

        Args:
            col: Pixel column index.
            row: Pixel row index.
            mm_per_dot: Pixel pitch in mm.
            x_offset: Image X origin in SVG units.
            y_offset: Image Y origin in SVG units.
            is_horizontal: Whether the scan axis is X.
            entering: True for the entry edge, False for the exit edge.
            reversed_pass: Whether this pass runs in reverse.

        Returns:
            ``(sx, sy)`` coordinate pair.
        """
        # For the scan axis, pick left (col*d) or right ((col+1)*d) edge.
        # Forward enter / Reverse exit  → left  edge = col * d
        # Forward exit  / Reverse enter → right edge = (col + 1) * d
        use_right = (entering == reversed_pass)
        if is_horizontal:
            sx = x_offset + (col + (1 if use_right else 0)) * mm_per_dot
            sy = y_offset + row * mm_per_dot
        else:
            sx = x_offset + col * mm_per_dot
            sy = y_offset + (row + (1 if use_right else 0)) * mm_per_dot
        return sx, sy