#!/usr/bin/env python3
 # 
 # This file is part of the InkBurn distribution (https://github.com/lgiuliani/InkBurn).
 # Copyright (c) 2025 LLaurent Giuliani.
 # 
 # This program is free software: you can redistribute it and/or modify  
 # it under the terms of the GNU General Public License as published by  
 # the Free Software Foundation, version 3.
 #
 # This program is distributed in the hope that it will be useful, but 
 # WITHOUT ANY WARRANTY; without even the implied warranty of 
 # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
 # General Public License for more details.
 #
 # You should have received a copy of the GNU General Public License 
 # along with this program. If not, see <http://www.gnu.org/licenses/>.
 #
import os
from lxml import etree
import inkex
from inkex.paths import CubicSuperPath
from inkex import Rectangle, Circle, Ellipse, Line, Polyline, Polygon, TextElement

NS = { 'svg': 'http://www.w3.org/2000/svg',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape'}

def list_layers(svg: etree) -> list[etree.Element]:
    """Get all layers from the SVG document."""
    layers = svg.xpath('//svg:g[@inkscape:groupmode="layer"]', namespaces=NS)
    if not layers:
        return []
    return (reversed(layers))

def get_layer_name(layer: etree) -> str:
    """Get the name of the layer, falling back to 'Unnamed Layer' if not set."""
    name = layer.get('{'+NS['inkscape']+'}label') or layer.get('id')
    return name if name else "Unnamed Layer"

def is_visible(elem: etree) -> bool:
    """Return False if element or parent are display:none."""
    while elem is not None:
        style = elem.get('style') or ''
        if 'display:none' in style.replace(' ', '').lower():
            return False
        elem = elem.getparent()
    return True

def get_sorted_elements(layer: etree) -> list:
    """Collect and sort all visible shape elements in a layer"""
    elements = []
    for elem in layer.xpath('.//svg:*', namespaces=NS):
        if not is_visible(elem):
            continue
            
        # Skip group elements - we'll process their children instead
        if elem.tag_name == 'g':
            continue

        # Skip elements without path representation
        if not hasattr(elem, 'path') : #or not callable(elem.path):
            inkex.utils.debug(f"Skipping unsupported element: {elem.tag_name} with id {elem.get('id', '')}")    
            continue

        elements.append(elem)
    
    # Sort elements for optimal cutting path (left to right, top to bottom)
    #return sorted(elements, key=lambda e: (e.bounding_box().x, e.bounding_box().y))
    return elements

def get_element_points(elem):
    tag = etree.QName(elem).localname
    if tag == 'path':
        d = elem.get('d')
        if d:
            sp = CubicSuperPath(d)
    elif tag in {'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'text'}:
        sp = elem.get_path().to_superpath()

    if sp:
        return [tuple(seg[1]) for sub in sp for seg in sub]

    return None