"""SVG layer and shape helpers for InkBurn.

Layer discovery, visibility checks, and per-layer element filtering
used by the export pipeline, SVG optimization, and persistence.
"""

from itertools import chain
from typing import List

from lxml import etree

from constants import NS, inkscape_qname


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
    name = layer.get(inkscape_qname("label")) or layer.get("id")
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
