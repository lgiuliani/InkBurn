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

def is_shape_element(elem: etree._Element) -> bool:
    """Check if an element is a shape that can be exported.

    Excludes groups, images, and elements without a ``path`` attribute.

    Args:
        elem: SVG element.

    Returns:
        True if the element is a shape.
    """
    return (
        elem.tag_name != "g"
        and elem.tag_name != "image"
        and hasattr(elem, "path")
    )


from collections.abc import Iterator

def iter_visible_shapes(layer: etree._Element) -> Iterator[etree._Element]:
    """
    Yield visible shapes belonging strictly to this layer.

    Nested layers are excluded to prevent geometry
    ownership leakage across layers.
    """

    stack = list(layer)
    while stack:
        elem = stack.pop(0)

        if is_visible(elem) and is_shape_element(elem):
            yield elem

        stack.extend(list(elem))

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
