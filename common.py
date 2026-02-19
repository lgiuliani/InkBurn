"""SVG utility functions for InkBurn extension.

Provides layer discovery, visibility checks, and element filtering
used by both the export pipeline and UI components.
"""

import logging
import math
from typing import List, Tuple

from inkex.transforms import Transform
from lxml import etree

from constants import INKSCAPE_NS, NS

logger = logging.getLogger(__name__)


def list_layers(svg: etree._Element) -> List[etree._Element]:
    """Get all layers from the SVG document in document order.

    Args:
        svg: Root ``<svg>`` element.

    Returns:
        Layers in bottom-to-top visual order
        (i.e., reversed XML document order).
    """
    layers = svg.xpath(
        '//svg:g[@inkscape:groupmode="layer"]', namespaces=NS
    )
    return list(reversed(layers)) if layers else []


def get_layer_name(layer: etree._Element) -> str:
    """Get the human-readable name of a layer element.

    Args:
        layer: Layer ``<g>`` element.

    Returns:
        Label string, falling back to ``id`` or ``"Unnamed Layer"``.
    """
    name = layer.get(f"{{{INKSCAPE_NS}}}label") or layer.get("id")
    return name if name else "Unnamed Layer"


def is_visible(elem: etree._Element) -> bool:
    """Check whether an element is visible.

    Walks up the tree; returns False if any ancestor has
    ``display:none`` in its style.

    Args:
        elem: SVG element.

    Returns:
        True if the element is displayed.
    """
    return not any(
        "display:none" in (e.get("style") or "").replace(" ", "").lower()
        for e in chain([elem], elem.iterancestors())
    )


def get_visible_shapes(layer: etree._Element) -> List[etree._Element]:
    """Collect all visible shape elements in a layer.

    Skips groups, images, and elements without a ``path`` attribute.

    Args:
        layer: Layer ``<g>`` element.

    Returns:
        Ordered list of shape elements.
    """
    elements: List[etree._Element] = []
    for elem in layer.xpath(".//svg:*", namespaces=NS):
        if not is_visible(elem):
            continue
        if elem.tag_name == "g":
            continue
        if elem.tag_name == "image":
            continue
        if not hasattr(elem, "path"):
            continue
        elements.append(elem)
    return elements


def get_image_elements(layer: etree._Element) -> List[etree._Element]:
    """Collect all visible ``<image>`` elements in a layer.

    Args:
        layer: Layer ``<g>`` element.

    Returns:
        List of ``<image>`` elements.
    """
    return [
        elem for elem in layer.xpath(".//svg:image", namespaces=NS)
        if is_visible(elem)
    ]


def layer_distance(
    layer: etree._Element,
    start_point: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[float, float, Tuple[float, float]]:
    """Calculate engrave and travel distances for a layer.

    Args:
        layer: Layer ``<g>`` element.
        start_point: Starting position as (x, y).

    Returns:
        Tuple of (engrave_distance, travel_distance, end_point).
    """
    elements = get_visible_shapes(layer)

    engrave = 0.0
    travel = 0.0
    last_point = start_point

    for elem in elements:
        transform = Transform(elem.composed_transform())
        path = elem.path.transform(transform)
        superpath = path.to_superpath()
        if not superpath:
            continue

        for subpath in superpath:
            for p1, p2 in zip(subpath[:-1], subpath[1:]):
                engrave += math.dist(p1[1], p2[1])
            travel += math.dist(last_point, subpath[0][1])
            last_point = subpath[-1][1]

    return engrave, travel, last_point
