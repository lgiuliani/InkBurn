"""SVG I/O bridge for config_core UI.

Thin wrapper around ``persistence.svg_io`` to maintain backward
compatibility with the layer configuration dialog.
"""

from typing import Dict, List, Tuple

import inkex
from lxml import etree

from models.layer import Layer
from persistence.svg_io import load_layers as _load_layers
from persistence.svg_io import save_layers as _save_layers


def load_layers(
    svg_root: etree._Element,
) -> Tuple[List[Layer], Dict[str, etree._Element]]:
    """Load layers from SVG.

    Args:
        svg_root: Root SVG element.

    Returns:
        Tuple of (ordered layer list, element mapping).
    """
    return _load_layers(svg_root)


def save_layers(
    layers: List[Layer],
    elements: Dict[str, etree._Element],
) -> int:
    """Save layers back to SVG elements.

    Args:
        layers: Layers to persist.
        elements: Layer id to SVG element mapping.

    Returns:
        Number of layers saved.
    """
    return _save_layers(layers, elements)
