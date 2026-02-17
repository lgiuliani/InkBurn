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
import math
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

    Each scan line contains per-pixel power values derived from the
    image grayscale.  The caller (G-code generator) is responsible for
    emitting the appropriate S values.

    Attributes:
        dpi: Output resolution in dots per inch.
        direction: Scan direction — ``"horizontal"`` or ``"vertical"``.
    """

    def __init__(
        self,
        dpi: int = 300,
        direction: str = "horizontal",
    ) -> None:
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
            job: Job supplying power_min / power_max.

        Returns:
            List of (PathSegment, power_list) tuples. Each segment is a
            single scan line; power_list contains per-pixel S values
            corresponding to each point in the segment.
        """
        if Image is None:
            logger.error("Pillow not installed — cannot process raster job")
            return []

        img = self._decode_image(element)
        if img is None:
            return []

        # Image placement in SVG coordinates
        x_offset = float(element.get("x", "0"))
        y_offset = float(element.get("y", "0"))
        img_width = float(element.get("width", str(img.width)))
        img_height = float(element.get("height", str(img.height)))

        transform = Transform(element.composed_transform())

        # Calculate pixel pitch
        mm_per_dot = 25.4 / self.dpi
        cols = max(1, int(img_width / mm_per_dot))
        rows = max(1, int(img_height / mm_per_dot))

        # Resample to target resolution
        gray = img.convert("L").resize((cols, rows), Image.LANCZOS)
        pixels = gray.load()

        return self._generate_scanlines(
            pixels, cols, rows, mm_per_dot,
            x_offset, y_offset, img_width, img_height,
            viewbox_height, transform, job,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _decode_image(
        self, element: etree._Element
    ) -> Optional["Image.Image"]:
        """Decode an ``<image>`` element's href to a PIL Image.

        Args:
            element: SVG ``<image>`` element.

        Returns:
            PIL Image or None on failure.
        """
        href = (
            element.get("{http://www.w3.org/1999/xlink}href")
            or element.get("href")
            or ""
        )
        if href.startswith("data:"):
            # Base-64 encoded inline image
            try:
                header, data = href.split(",", 1)
                raw = base64.b64decode(data)
                return Image.open(io.BytesIO(raw))
            except Exception:
                logger.error("Failed to decode inline image data")
                return None
        elif href:
            try:
                return Image.open(href)
            except Exception:
                logger.error("Failed to open image file: %s", href)
                return None
        return None

    def _generate_scanlines(
        self,
        pixels: object,
        cols: int,
        rows: int,
        mm_per_dot: float,
        x_offset: float,
        y_offset: float,
        img_width: float,
        img_height: float,
        viewbox_height: float,
        transform: Transform,
        job: Job,
    ) -> List[Tuple[PathSegment, List[int]]]:
        """Generate scan-line segments from pixel data.

        Args:
            pixels: PIL pixel access object.
            cols: Number of pixel columns.
            rows: Number of pixel rows.
            mm_per_dot: Physical size of one pixel in mm.
            x_offset: Image X position in SVG.
            y_offset: Image Y position in SVG.
            img_width: Image width in SVG units.
            img_height: Image height in SVG units.
            viewbox_height: SVG viewbox height for Y flip.
            transform: Composed transform for the element.
            job: Job supplying power range.

        Returns:
            List of (segment, power_list) tuples with per-pixel S values.
        """
        results: List[Tuple[PathSegment, List[int]]] = []
        power_range = job.power_max - job.power_min

        if self.direction == "horizontal":
            results = self._horizontal_scan(
                pixels, cols, rows, mm_per_dot,
                x_offset, y_offset, viewbox_height,
                transform, job.power_min, power_range,
            )
        else:
            results = self._vertical_scan(
                pixels, cols, rows, mm_per_dot,
                x_offset, y_offset, viewbox_height,
                transform, job.power_min, power_range,
            )

        return results

    def _pixel_to_power(
        self, pixel_value: int, power_min: float, power_range: float
    ) -> int:
        """Map a grayscale pixel value to laser power.

        White (255) → power_min, Black (0) → power_min + power_range.

        Args:
            pixel_value: Grayscale intensity 0-255.
            power_min: Minimum power S value.
            power_range: power_max minus power_min.

        Returns:
            Computed S value.
        """
        intensity = 1.0 - (pixel_value / 255.0)
        return int(power_min + intensity * power_range)

    def _horizontal_scan(
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
        """Generate horizontal scan lines.

        Args:
            pixels: PIL pixel access object.
            cols: Pixel columns.
            rows: Pixel rows.
            mm_per_dot: Pixel pitch in mm.
            x_offset: SVG X offset.
            y_offset: SVG Y offset.
            viewbox_height: SVG viewbox height.
            transform: Element transform.
            power_min: Minimum power.
            power_range: Power range.

        Returns:
            List of (segment, power_list) tuples with per-pixel S values.
        """
        results: List[Tuple[PathSegment, List[int]]] = []

        for row in range(rows):
            points: List[Vector2d] = []
            powers: List[int] = []

            col_range = range(cols) if row % 2 == 0 else range(cols - 1, -1, -1)
            for col in col_range:
                sx = x_offset + col * mm_per_dot
                sy = y_offset + row * mm_per_dot
                tx, ty = transform.apply_to_point((sx, sy))
                points.append(Vector2d(tx, viewbox_height - ty))

                power = self._pixel_to_power(pixels[col, row], power_min, power_range)
                powers.append(power)

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

    def _vertical_scan(
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
        """Generate vertical scan lines.

        Args:
            pixels: PIL pixel access object.
            cols: Pixel columns.
            rows: Pixel rows.
            mm_per_dot: Pixel pitch in mm.
            x_offset: SVG X offset.
            y_offset: SVG Y offset.
            viewbox_height: SVG viewbox height.
            transform: Element transform.
            power_min: Minimum power.
            power_range: Power range.

        Returns:
            List of (segment, power_list) tuples with per-pixel S values.
        """
        results: List[Tuple[PathSegment, List[int]]] = []

        for col in range(cols):
            points: List[Vector2d] = []
            powers: List[int] = []

            row_range = range(rows) if col % 2 == 0 else range(rows - 1, -1, -1)
            for row in row_range:
                sx = x_offset + col * mm_per_dot
                sy = y_offset + row * mm_per_dot
                tx, ty = transform.apply_to_point((sx, sy))
                points.append(Vector2d(tx, viewbox_height - ty))

                power = self._pixel_to_power(pixels[col, row], power_min, power_range)
                powers.append(power)

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
