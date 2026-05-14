"""SVG style and paint helpers for InkBurn export.

This module resolves fill visibility, fill rules, solid paint colors, and
gradient sampling so the exporter can stay focused on job orchestration.
"""

import math
import re
from typing import Dict, List, Optional, Set, Tuple

import inkex
from inkex.transforms import Vector2d
from lxml import etree

from models.job import Job
from models.path import PathSegment

RGBColor = Tuple[float, float, float]
RGBAColor = Tuple[float, float, float, float]
BBox = Tuple[float, float, float, float]
Matrix = Tuple[float, float, float, float, float, float]

_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_TRANSFORM_RE = re.compile(r"([a-zA-Z]+)\(([^)]*)\)")
_URL_RE = re.compile(r"url\(\s*['\"]?#([^'\")\s]+)['\"]?\s*\)")


def _parse_style(style: str) -> Dict[str, str]:
    """Parse an inline SVG style attribute into lowercase property names."""
    declarations: Dict[str, str] = {}
    for declaration in style.split(";"):
        if ":" not in declaration:
            continue
        name, value = declaration.split(":", 1)
        declarations[name.strip().lower()] = value.strip()
    return declarations


def _local_style_property(elem: etree._Element, name: str) -> Optional[str]:
    """Read a style property from inline CSS or a presentation attribute."""
    name = name.lower()
    value = _parse_style(elem.get("style") or "").get(name)
    if value is not None:
        return value
    return elem.get(name)


def _inherited_style_property(elem: etree._Element, name: str) -> Optional[str]:
    """Resolve a simple inherited SVG style property from element ancestors."""
    for current in [elem, *elem.iterancestors()]:
        value = _local_style_property(current, name)
        if value is not None:
            return value
    return None


def _parse_opacity(value: Optional[str]) -> Optional[float]:
    """Parse an SVG opacity value, returning None when it is not numeric."""
    if value is None:
        return None

    value = value.strip()
    try:
        if value.endswith("%"):
            return float(value[:-1]) / 100.0
        return float(value)
    except ValueError:
        return None


def _is_transparent_paint(value: str) -> bool:
    """Return True when an SVG paint value represents no visible paint."""
    normalized = value.strip().lower().replace(" ", "")
    if normalized in {"none", "transparent"}:
        return True
    if normalized.startswith("#") and len(normalized) in {5, 9}:
        return normalized[-2:] == "00"
    if normalized.startswith(
        ("rgb(", "rgba(", "hsl(", "hsla(")
    ) and normalized.endswith(")"):
        body = normalized.split("(", 1)[1][:-1]
        if "/" in body:
            alpha = body.rsplit("/", 1)[-1]
        elif normalized.startswith(("rgba(", "hsla(")):
            alpha = body.rsplit(",", 1)[-1]
        else:
            return False
        return _parse_opacity(alpha) == 0
    return False


def _clamp_color_channel(value: float) -> float:
    """Clamp one RGB channel to the CSS 0..255 range."""
    return max(0.0, min(value, 255.0))


def _parse_color_channel(value: str) -> Optional[float]:
    """Parse an RGB color channel from a number or percentage."""
    value = value.strip()
    try:
        if value.endswith("%"):
            return _clamp_color_channel(float(value[:-1]) * 2.55)
        return _clamp_color_channel(float(value))
    except ValueError:
        return None


def _parse_rgb_function(value: str) -> Optional[RGBColor]:
    """Parse ``rgb(...)`` or ``rgba(...)`` CSS color syntax."""
    body = value.split("(", 1)[1].rsplit(")", 1)[0]
    parts = body.replace(",", " ").replace("/", " ").split()
    if len(parts) < 3:
        return None

    channels: List[float] = []
    for part in parts[:3]:
        channel = _parse_color_channel(part)
        if channel is None:
            return None
        channels.append(channel)
    return channels[0], channels[1], channels[2]


def _parse_hue(value: str) -> Optional[float]:
    """Parse a CSS hue value and return degrees."""
    value = value.strip()
    try:
        if value.endswith("deg"):
            return float(value[:-3])
        if value.endswith("turn"):
            return float(value[:-4]) * 360.0
        if value.endswith("rad"):
            return math.degrees(float(value[:-3]))
        return float(value)
    except ValueError:
        return None


def _parse_percentage(value: str) -> Optional[float]:
    """Parse a CSS percentage into a 0..1 ratio."""
    value = value.strip()
    try:
        if value.endswith("%"):
            return max(0.0, min(float(value[:-1]) / 100.0, 1.0))
        return max(0.0, min(float(value), 1.0))
    except ValueError:
        return None


def _hue_to_rgb(p: float, q: float, t: float) -> float:
    """Convert one HSL hue component to an RGB ratio."""
    if t < 0:
        t += 1
    if t > 1:
        t -= 1
    if t < 1 / 6:
        return p + (q - p) * 6 * t
    if t < 1 / 2:
        return q
    if t < 2 / 3:
        return p + (q - p) * (2 / 3 - t) * 6
    return p


def _parse_hsl_function(value: str) -> Optional[RGBColor]:
    """Parse ``hsl(...)`` or ``hsla(...)`` CSS color syntax."""
    body = value.split("(", 1)[1].rsplit(")", 1)[0]
    parts = body.replace(",", " ").replace("/", " ").split()
    if len(parts) < 3:
        return None

    hue = _parse_hue(parts[0])
    saturation = _parse_percentage(parts[1])
    lightness = _parse_percentage(parts[2])
    if hue is None or saturation is None or lightness is None:
        return None

    hue = (hue % 360.0) / 360.0
    if saturation == 0:
        gray = lightness * 255.0
        return gray, gray, gray

    q = (
        lightness * (1 + saturation)
        if lightness < 0.5
        else lightness + saturation - lightness * saturation
    )
    p = 2 * lightness - q
    return (
        _hue_to_rgb(p, q, hue + 1 / 3) * 255.0,
        _hue_to_rgb(p, q, hue) * 255.0,
        _hue_to_rgb(p, q, hue - 1 / 3) * 255.0,
    )


def _parse_hex_color(value: str) -> Optional[RGBColor]:
    """Parse CSS hexadecimal color syntax."""
    digits = value[1:]
    if len(digits) in {3, 4}:
        digits = "".join(char * 2 for char in digits[:3])
    elif len(digits) in {6, 8}:
        digits = digits[:6]
    else:
        return None

    try:
        return (
            float(int(digits[0:2], 16)),
            float(int(digits[2:4], 16)),
            float(int(digits[4:6], 16)),
        )
    except ValueError:
        return None


def _coerce_inkex_color_channel(value: object) -> Optional[float]:
    """Coerce a channel from inkex's color objects into 0..255."""
    try:
        channel = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

    if 0.0 <= channel <= 1.0:
        return channel * 255.0
    return _clamp_color_channel(channel)


def _parse_inkex_color(value: str) -> Optional[RGBColor]:
    """Let Inkscape parse CSS colors such as named colors."""
    try:
        color = inkex.Color(value)
    except Exception:
        return None

    for method_name in ("to_rgb", "to_rgba"):
        method = getattr(color, method_name, None)
        if method is None:
            continue
        try:
            converted = method()
        except Exception:
            continue
        rgb = _coerce_inkex_color(converted)
        if rgb is not None:
            return rgb

    return _coerce_inkex_color(color)


def _coerce_inkex_color(color: object) -> Optional[RGBColor]:
    """Extract RGB channels from several possible inkex color shapes."""
    if isinstance(color, str):
        return _parse_hex_color(color) if color.startswith("#") else None

    channels: List[float] = []
    try:
        values = list(color)  # type: ignore[arg-type]
    except TypeError:
        values = []

    if len(values) >= 3:
        for value in values[:3]:
            channel = _coerce_inkex_color_channel(value)
            if channel is None:
                return None
            channels.append(channel)
        return channels[0], channels[1], channels[2]

    attrs = ("red", "green", "blue")
    if all(hasattr(color, attr) for attr in attrs):
        for attr in attrs:
            channel = _coerce_inkex_color_channel(getattr(color, attr))
            if channel is None:
                return None
            channels.append(channel)
        return channels[0], channels[1], channels[2]

    return None


def _parse_css_color(value: str) -> Optional[RGBColor]:
    """Parse a simple SVG/CSS color into RGB channels."""
    normalized = value.strip().lower()
    if normalized.startswith("#"):
        return _parse_hex_color(normalized)
    if normalized.startswith(("rgb(", "rgba(")) and normalized.endswith(")"):
        return _parse_rgb_function(normalized)
    if normalized.startswith(("hsl(", "hsla(")) and normalized.endswith(")"):
        return _parse_hsl_function(normalized)
    if normalized in {"none", "transparent"}:
        return None
    parsed = _parse_inkex_color(normalized)
    if parsed is not None:
        return parsed
    return None


def _paint_fallback(value: str) -> Optional[str]:
    """Return a direct paint color or the fallback color after ``url(...)``."""
    paint = value.strip()
    if not paint.lower().startswith("url("):
        return paint

    end = paint.find(")")
    if end < 0:
        return None
    fallback = paint[end + 1 :].strip()
    return fallback or None


def _paint_url_id(value: str) -> Optional[str]:
    """Return the target id from ``url(#id)`` paint syntax."""
    match = _URL_RE.search(value.strip())
    return match.group(1) if match else None


def _local_name(elem: etree._Element) -> str:
    """Return an element's local tag name without namespace."""
    return etree.QName(elem).localname


def _find_element_by_id(
    elem: etree._Element,
    element_id: str,
) -> Optional[etree._Element]:
    """Find an SVG document element by id."""
    root = elem.getroottree().getroot()
    for candidate in root.iter():
        if candidate.get("id") == element_id:
            return candidate
    return None


def _href_id(elem: etree._Element) -> Optional[str]:
    """Return a referenced id from an href attribute."""
    href = elem.get(_XLINK_HREF) or elem.get("href")
    if href and href.startswith("#"):
        return href[1:]
    return None


def _gradient_chain(gradient: etree._Element) -> List[etree._Element]:
    """Return a gradient followed by its inherited href chain."""
    chain: List[etree._Element] = []
    seen: Set[str] = set()
    current: Optional[etree._Element] = gradient

    while current is not None:
        chain.append(current)
        href = _href_id(current)
        if href is None or href in seen:
            break
        seen.add(href)
        current = _find_element_by_id(current, href)

    return chain


def _gradient_attr(
    chain: List[etree._Element],
    name: str,
    default: str,
) -> str:
    """Resolve a gradient attribute through its href chain."""
    for gradient in chain:
        value = gradient.get(name)
        if value is not None:
            return value
    return default


def _gradient_stop_elements(chain: List[etree._Element]) -> List[etree._Element]:
    """Return the first direct stop list found in a gradient chain."""
    for gradient in chain:
        stops = [child for child in gradient if _local_name(child) == "stop"]
        if stops:
            return stops
    return []


def _parse_offset(value: Optional[str]) -> float:
    """Parse and clamp an SVG gradient stop offset."""
    if value is None:
        return 0.0
    try:
        if value.strip().endswith("%"):
            return max(0.0, min(float(value.strip()[:-1]) / 100.0, 1.0))
        return max(0.0, min(float(value), 1.0))
    except ValueError:
        return 0.0


def _blend_over_white(rgb: RGBColor, alpha: float) -> RGBColor:
    """Composite an RGB color over white using alpha."""
    alpha = max(0.0, min(alpha, 1.0))
    return tuple(channel * alpha + 255.0 * (1.0 - alpha) for channel in rgb)


def _effective_fill_opacity(elem: etree._Element) -> float:
    """Resolve inherited fill opacity and parent opacity as one alpha."""
    opacity = _parse_opacity(_inherited_style_property(elem, "fill-opacity"))
    alpha = 1.0 if opacity is None else opacity

    for current in [elem, *elem.iterancestors()]:
        current_opacity = _parse_opacity(_local_style_property(current, "opacity"))
        if current_opacity is not None:
            alpha *= current_opacity

    return max(0.0, min(alpha, 1.0))


def _stop_rgba(stop: etree._Element) -> RGBAColor:
    """Resolve a gradient stop color and opacity."""
    color_value = _local_style_property(stop, "stop-color") or "black"
    if color_value.strip().lower() == "currentcolor":
        color_value = _inherited_style_property(stop, "color") or "black"

    rgb = _parse_css_color(color_value) or (0.0, 0.0, 0.0)
    opacity = _parse_opacity(_local_style_property(stop, "stop-opacity"))
    alpha = 1.0 if opacity is None else opacity
    return rgb[0], rgb[1], rgb[2], max(0.0, min(alpha, 1.0))


def _gradient_stops(chain: List[etree._Element]) -> List[Tuple[float, RGBAColor]]:
    """Resolve sorted color stops for a gradient."""
    stops = [
        (_parse_offset(stop.get("offset")), _stop_rgba(stop))
        for stop in _gradient_stop_elements(chain)
    ]
    if not stops:
        return [(0.0, (0.0, 0.0, 0.0, 1.0)), (1.0, (0.0, 0.0, 0.0, 1.0))]
    return sorted(stops, key=lambda stop: stop[0])


def _interpolate_stops(stops: List[Tuple[float, RGBAColor]], t: float) -> RGBColor:
    """Interpolate a gradient stop list at a normalized position."""
    t = max(0.0, min(t, 1.0))
    if t <= stops[0][0]:
        return _blend_over_white(stops[0][1][:3], stops[0][1][3])

    for (left_offset, left), (right_offset, right) in zip(stops, stops[1:]):
        if t > right_offset:
            continue
        span = right_offset - left_offset
        ratio = 0.0 if span <= 0 else (t - left_offset) / span
        rgb = (
            left[0] + (right[0] - left[0]) * ratio,
            left[1] + (right[1] - left[1]) * ratio,
            left[2] + (right[2] - left[2]) * ratio,
        )
        alpha = left[3] + (right[3] - left[3]) * ratio
        return _blend_over_white(rgb, alpha)

    return _blend_over_white(stops[-1][1][:3], stops[-1][1][3])


def _parse_transform_numbers(value: str) -> List[float]:
    """Parse an SVG transform argument list."""
    parts = [part for part in re.split(r"[,\s]+", value.strip()) if part]
    try:
        return [float(part) for part in parts]
    except ValueError:
        return []


def _matrix_multiply(left: Matrix, right: Matrix) -> Matrix:
    """Multiply two SVG affine matrices."""
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _translate_matrix(tx: float, ty: float = 0.0) -> Matrix:
    """Build an SVG translation matrix."""
    return 1.0, 0.0, 0.0, 1.0, tx, ty


def _transform_command_matrix(name: str, nums: List[float]) -> Matrix:
    """Build a matrix for one SVG transform command."""
    name = name.lower()
    if name == "matrix" and len(nums) >= 6:
        return nums[0], nums[1], nums[2], nums[3], nums[4], nums[5]
    if name == "translate" and nums:
        return _translate_matrix(nums[0], nums[1] if len(nums) > 1 else 0.0)
    if name == "scale" and nums:
        return nums[0], 0.0, 0.0, nums[1] if len(nums) > 1 else nums[0], 0.0, 0.0
    if name == "rotate" and nums:
        rad = math.radians(nums[0])
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        rotate = cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0
        if len(nums) >= 3:
            cx, cy = nums[1], nums[2]
            return _matrix_multiply(
                _matrix_multiply(_translate_matrix(cx, cy), rotate),
                _translate_matrix(-cx, -cy),
            )
        return rotate
    if name == "skewx" and nums:
        return 1.0, 0.0, math.tan(math.radians(nums[0])), 1.0, 0.0, 0.0
    if name == "skewy" and nums:
        return 1.0, math.tan(math.radians(nums[0])), 0.0, 1.0, 0.0, 0.0
    return 1.0, 0.0, 0.0, 1.0, 0.0, 0.0


def _parse_transform(value: Optional[str]) -> Matrix:
    """Parse a subset of SVG transform syntax into a matrix."""
    matrix: Matrix = 1.0, 0.0, 0.0, 1.0, 0.0, 0.0
    if not value:
        return matrix

    for name, raw_args in _TRANSFORM_RE.findall(value):
        command = _transform_command_matrix(name, _parse_transform_numbers(raw_args))
        matrix = _matrix_multiply(matrix, command)
    return matrix


def _invert_matrix(matrix: Matrix) -> Optional[Matrix]:
    """Invert an SVG affine matrix."""
    a, b, c, d, e, f = matrix
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    return (
        d / det,
        -b / det,
        -c / det,
        a / det,
        (c * f - d * e) / det,
        (b * e - a * f) / det,
    )


def _apply_matrix(matrix: Matrix, x: float, y: float) -> Tuple[float, float]:
    """Apply an SVG affine matrix to a point."""
    a, b, c, d, e, f = matrix
    return a * x + c * y + e, b * x + d * y + f


def _apply_gradient_transform(
    chain: List[etree._Element],
    x: float,
    y: float,
) -> Tuple[float, float]:
    """Move a document point into gradient coordinate space."""
    transform = _parse_transform(_gradient_attr(chain, "gradientTransform", ""))
    inverse = _invert_matrix(transform)
    if inverse is None:
        return x, y
    return _apply_matrix(inverse, x, y)


def _parse_length(value: Optional[str], reference: float, default: float) -> float:
    """Parse an SVG length or percentage."""
    if value is None:
        return default
    value = value.strip()
    try:
        if value.endswith("%"):
            return float(value[:-1]) / 100.0 * reference
        return float(value)
    except ValueError:
        return default


def _bbox_size(bbox: BBox) -> Tuple[float, float]:
    """Return non-zero bbox dimensions."""
    min_x, min_y, max_x, max_y = bbox
    return max(max_x - min_x, 1e-9), max(max_y - min_y, 1e-9)


def _linear_gradient_point(
    chain: List[etree._Element],
    bbox: BBox,
) -> Tuple[float, float, float, float]:
    """Resolve linear gradient endpoints in document coordinates."""
    min_x, min_y, _, _ = bbox
    width, height = _bbox_size(bbox)
    units = _gradient_attr(chain, "gradientUnits", "objectBoundingBox")

    if units == "userSpaceOnUse":
        x1 = _parse_length(_gradient_attr(chain, "x1", "0%"), width, min_x)
        y1 = _parse_length(_gradient_attr(chain, "y1", "0%"), height, min_y)
        x2 = _parse_length(
            _gradient_attr(chain, "x2", "100%"),
            width,
            min_x + width,
        )
        y2 = _parse_length(_gradient_attr(chain, "y2", "0%"), height, min_y)
        return x1, y1, x2, y2

    x1 = min_x + _parse_length(_gradient_attr(chain, "x1", "0%"), 1.0, 0.0) * width
    y1 = min_y + _parse_length(_gradient_attr(chain, "y1", "0%"), 1.0, 0.0) * height
    x2 = min_x + _parse_length(_gradient_attr(chain, "x2", "100%"), 1.0, 1.0) * width
    y2 = min_y + _parse_length(_gradient_attr(chain, "y2", "0%"), 1.0, 0.0) * height
    return x1, y1, x2, y2


def _apply_spread(t: float, spread: str) -> float:
    """Apply SVG spreadMethod behavior to a gradient position."""
    if spread == "repeat":
        return t % 1.0
    if spread == "reflect":
        t = abs(t) % 2.0
        return t if t <= 1.0 else 2.0 - t
    return max(0.0, min(t, 1.0))


def _sample_linear_gradient(
    chain: List[etree._Element],
    point: Vector2d,
    viewbox_height: float,
    bbox: BBox,
) -> RGBColor:
    """Sample a linear gradient at a machine-space point."""
    x, y = _apply_gradient_transform(chain, point.x, viewbox_height - point.y)
    x1, y1, x2, y2 = _linear_gradient_point(chain, bbox)
    dx = x2 - x1
    dy = y2 - y1
    denom = dx * dx + dy * dy
    t = 0.0 if denom <= 1e-12 else ((x - x1) * dx + (y - y1) * dy) / denom
    t = _apply_spread(t, _gradient_attr(chain, "spreadMethod", "pad"))
    return _interpolate_stops(_gradient_stops(chain), t)


def _sample_radial_gradient(
    chain: List[etree._Element],
    point: Vector2d,
    viewbox_height: float,
    bbox: BBox,
) -> RGBColor:
    """Sample a radial gradient at a machine-space point."""
    x, y = _apply_gradient_transform(chain, point.x, viewbox_height - point.y)
    min_x, min_y, _, _ = bbox
    width, height = _bbox_size(bbox)
    units = _gradient_attr(chain, "gradientUnits", "objectBoundingBox")

    if units == "userSpaceOnUse":
        cx = _parse_length(
            _gradient_attr(chain, "cx", "50%"),
            width,
            min_x + width / 2,
        )
        cy = _parse_length(
            _gradient_attr(chain, "cy", "50%"),
            height,
            min_y + height / 2,
        )
        max_size = max(width, height)
        r = _parse_length(
            _gradient_attr(chain, "r", "50%"),
            max_size,
            max_size / 2,
        )
        distance = math.hypot(x - cx, y - cy)
    else:
        px = (x - min_x) / width
        py = (y - min_y) / height
        cx = _parse_length(_gradient_attr(chain, "cx", "50%"), 1.0, 0.5)
        cy = _parse_length(_gradient_attr(chain, "cy", "50%"), 1.0, 0.5)
        r = _parse_length(_gradient_attr(chain, "r", "50%"), 1.0, 0.5)
        distance = math.hypot(px - cx, py - cy)

    t = 1.0 if r <= 1e-12 else distance / r
    t = _apply_spread(t, _gradient_attr(chain, "spreadMethod", "pad"))
    return _interpolate_stops(_gradient_stops(chain), t)


def _sample_gradient(
    gradient: etree._Element,
    point: Vector2d,
    viewbox_height: float,
    bbox: BBox,
) -> Optional[RGBColor]:
    """Sample a linear or radial gradient at a machine-space point."""
    chain = _gradient_chain(gradient)
    kind = _local_name(gradient)
    if kind == "linearGradient":
        return _sample_linear_gradient(chain, point, viewbox_height, bbox)
    if kind == "radialGradient":
        return _sample_radial_gradient(chain, point, viewbox_height, bbox)
    return None


def _fill_rgb(
    elem: etree._Element,
    point: Optional[Vector2d] = None,
    viewbox_height: float = 0.0,
    bbox: Optional[BBox] = None,
) -> Optional[RGBColor]:
    """Resolve the filled element's RGB color at a point, if available."""
    fill = _inherited_style_property(elem, "fill")
    paint = "black" if fill is None else fill.strip()

    gradient_id = _paint_url_id(paint)
    if gradient_id is not None and point is not None and bbox is not None:
        gradient = _find_element_by_id(elem, gradient_id)
        if gradient is not None:
            rgb = _sample_gradient(gradient, point, viewbox_height, bbox)
            if rgb is not None:
                return _blend_over_white(rgb, _effective_fill_opacity(elem))

    paint = _paint_fallback(paint)
    if paint is None:
        return None

    if paint.strip().lower() == "currentcolor":
        paint = _inherited_style_property(elem, "color") or "black"

    rgb = _parse_css_color(paint)
    if rgb is None:
        return None
    return _blend_over_white(rgb, _effective_fill_opacity(elem))


def fill_power(
    elem: etree._Element,
    job: Job,
    point: Optional[Vector2d] = None,
    viewbox_height: float = 0.0,
    bbox: Optional[BBox] = None,
) -> float:
    """Map an element fill color to the job's min/max power range."""
    rgb = _fill_rgb(elem, point, viewbox_height, bbox)
    if rgb is None:
        return job.power_max

    red, green, blue = rgb
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return job.power_min + (1.0 - luminance / 255.0) * (
        job.power_max - job.power_min
    )


def _fill_uses_gradient(elem: etree._Element) -> bool:
    """Return True when an element's fill resolves to a supported gradient."""
    fill = _inherited_style_property(elem, "fill")
    if fill is None:
        return False

    gradient_id = _paint_url_id(fill)
    if gradient_id is None:
        return False

    gradient = _find_element_by_id(elem, gradient_id)
    return gradient is not None and _local_name(gradient) in {
        "linearGradient",
        "radialGradient",
    }


def polygons_svg_bbox(
    polygons: List[List[Vector2d]],
    viewbox_height: float,
) -> BBox:
    """Calculate a document-space bbox from machine-space polygons."""
    xs = [point.x for polygon in polygons for point in polygon]
    ys = [viewbox_height - point.y for polygon in polygons for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _subdivide_points(points: List[Vector2d], max_step: float) -> List[Vector2d]:
    """Subdivide line segments so gradient power can change along them."""
    if len(points) < 2 or max_step <= 0:
        return points

    subdivided = [points[0]]
    for start, end in zip(points, points[1:]):
        length = math.hypot(end.x - start.x, end.y - start.y)
        steps = max(1, int(math.ceil(length / max_step)))
        for idx in range(1, steps + 1):
            ratio = idx / steps
            subdivided.append(
                Vector2d(
                    start.x + (end.x - start.x) * ratio,
                    start.y + (end.y - start.y) * ratio,
                )
            )
    return subdivided


def apply_fill_power_to_hatch(
    hatch: PathSegment,
    shape: etree._Element,
    job: Job,
    viewbox_height: float,
    bbox: BBox,
    gradient_sample_step: float,
) -> None:
    """Assign constant or per-point fill power to one hatch segment."""
    if _fill_uses_gradient(shape):
        hatch.points = _subdivide_points(hatch.points, gradient_sample_step)
        hatch.power = None
        hatch.powers = [
            fill_power(shape, job, point, viewbox_height, bbox)
            for point in hatch.points
        ]
        return

    hatch.power = fill_power(shape, job)
    hatch.powers = None


def has_visible_fill(elem: etree._Element) -> bool:
    """Check whether an element has a fill color visible enough to hatch."""
    fill = _inherited_style_property(elem, "fill")
    if fill is not None and _is_transparent_paint(fill):
        return False

    fill_opacity = _parse_opacity(_inherited_style_property(elem, "fill-opacity"))
    if fill_opacity == 0:
        return False

    for current in [elem, *elem.iterancestors()]:
        opacity = _parse_opacity(_local_style_property(current, "opacity"))
        if opacity == 0:
            return False

    return True


def fill_rule(elem: etree._Element) -> str:
    """Resolve the SVG fill rule used to hatch a filled element."""
    value = _inherited_style_property(elem, "fill-rule")
    if value is None:
        return "nonzero"

    normalized = value.strip().lower().replace("-", "")
    return "evenodd" if normalized == "evenodd" else "nonzero"
