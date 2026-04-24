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
        settings = MachineSettings(debug_level=DebugLevel.VERBOSE)

        with patch("debug_utils.inkex.utils.debug") as mock_debug:
            debug_output(settings, "hello", DebugLevel.MIN)

        mock_debug.assert_called_once_with("hello")

    def test_skips_when_level_is_too_low(self) -> None:
        """Messages above the configured level are suppressed."""
        settings = MachineSettings(debug_level=DebugLevel.OFF)

        with patch("debug_utils.inkex.utils.debug") as mock_debug:
            debug_output(settings, "hidden", DebugLevel.MIN)

        mock_debug.assert_not_called()
