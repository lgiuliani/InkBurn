#!/usr/bin/env python3
"""
Central constants for InkBurn extension.

This module consolidates all configuration constants used across the InkBurn
extension to ensure consistency and make maintenance easier.
"""

# =============================================================================
# XML/SVG Namespaces
# =============================================================================

NS = {
    'svg': 'http://www.w3.org/2000/svg',
    'inkscape': 'http://www.inkscape.org/namespaces/inkscape'
}

INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"


# =============================================================================
# G-Code Generation
# =============================================================================

SMAX = 1000              # Maximum laser power (S value)
TRAVEL_SPEED = 4000      # mm/min for travel moves (G0)
COORD_PRECISION = 2      # Decimal precision for coordinate output
GCODE_SEPARATOR = ''     # Separator between G-code command parts


# =============================================================================
# Path Processing
# =============================================================================

CURVE_PRECISION = 0.1    # mm per interpolation step for curve subdivision
CLOSED_PATH_TOLERANCE = 0.01  # Distance threshold to consider a path closed (mm)

