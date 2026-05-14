#!tests/test_debug_utils.py
"""Tests for filtered Inkscape debug output."""

import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from debug_utils import debug_output
from models.machine import DebugLevel, MachineSettings


class TestDebugOutput:
    """Debug message filtering tests."""

    def test_emits_when_level_is_allowed(self) -> None:
        """Messages at or below the configured level are emitted."""
        settings = MachineSettings(debug_level=DebugLevel.INFO)

        with patch("debug_utils.inkex.utils.debug") as mock_debug:
            debug_output(settings, "hello", DebugLevel.WARNING)

        mock_debug.assert_called_once_with("hello")

    def test_skips_when_level_is_too_verbose(self) -> None:
        """Messages more verbose than the configured level are suppressed."""
        settings = MachineSettings(debug_level=DebugLevel.CRITICAL)

        with patch("debug_utils.inkex.utils.debug") as mock_debug:
            debug_output(settings, "hidden", DebugLevel.INFO)

        mock_debug.assert_not_called()

    def test_emits_at_exact_configured_level(self) -> None:
        """Messages exactly at the configured level are emitted."""
        settings = MachineSettings(debug_level=DebugLevel.WARNING)

        with patch("debug_utils.inkex.utils.debug") as mock_debug:
            debug_output(settings, "visible", DebugLevel.WARNING)

        mock_debug.assert_called_once_with("visible")