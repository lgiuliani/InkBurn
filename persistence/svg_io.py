"""SVG I/O for layer and job data.

Reads and writes ``data-job-X`` JSON attributes on SVG layer ``<g>``
elements. Also handles cleaning stale attributes when jobs are removed.
"""

import logging
import re
from typing import Dict, List, Tuple

from lxml import etree

from constants import INKSCAPE_NS
from common import is_visible
from models.job import Job
from models.layer import Layer

logger = logging.getLogger(__name__)

_DATA_JOB_RE = re.compile(r"^data-job-(\d+)$")


def _is_layer(elem: etree._Element) -> bool:
    """Detect Inkscape layer groups.

    Args:
        elem: An SVG element.

    Returns:
        True if *elem* is an ``inkscape:groupmode="layer"`` group.
    """
    return elem.get(f"{{{INKSCAPE_NS}}}groupmode") == "layer"


def _get_layer_label(elem: etree._Element) -> str:
    """Return the human-readable label of a layer element.

    Args:
        elem: Layer ``<g>`` element.

    Returns:
        Label string from ``inkscape:label``, falling back to ``id``.
    """
    return elem.get(f"{{{INKSCAPE_NS}}}label") or elem.get("id") or "Unnamed"


def load_layers(
    svg_root: etree._Element,
) -> Tuple[List[Layer], Dict[str, etree._Element]]:
    """Load all layers and their jobs from an SVG root element.

    Layers are returned in SVG document order.

    Args:
        svg_root: Root ``<svg>`` element.

    Returns:
        Tuple of (ordered list of Layer models, mapping of layer_id → element).
    """
    layers: List[Layer] = []
    elements: Dict[str, etree._Element] = {}

    for elem in svg_root.iter():
        if not _is_layer(elem):
            continue
        layer_id = elem.get("id", "")
        label = _get_layer_label(elem)
        visible = is_visible(elem)
        attrs = dict(elem.attrib)

        layer = Layer.from_svg_attributes(layer_id, label, visible, attrs)
        layers.append(layer)
        elements[layer_id] = elem
        logger.debug("Loaded layer '%s': %s", label, layer.get_summary())

    return layers, elements


def save_layers(
    layers: List[Layer],
    elements: Dict[str, etree._Element],
) -> int:
    """Write layer/job data back to SVG elements.

    First cleans any stale ``data-job-X`` attributes, then writes
    the current job list.

    Args:
        layers: Layer models to persist.
        elements: Mapping of layer_id → SVG ``<g>`` element.

    Returns:
        Number of layers saved.
    """
    count = 0
    for layer in layers:
        elem = elements.get(layer.layer_id)
        if elem is None:
            continue
        clean_stale_job_attrs(elem)
        for key, value in layer.to_svg_attributes().items():
            elem.set(key, value)
        count += 1
    return count


def clean_stale_job_attrs(elem: etree._Element) -> None:
    """Remove all existing ``data-job-X`` attributes from an element.

    Args:
        elem: SVG element to clean.
    """
    keys_to_remove = [k for k in elem.attrib if _DATA_JOB_RE.match(k)]
    for key in keys_to_remove:
        del elem.attrib[key]
