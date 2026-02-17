"""Tests for machine settings persistence."""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from models.machine import DebugLevel, MachineSettings
from persistence.preferences import load_machine_settings, save_machine_settings


class TestMachineSettings:
    """Machine settings model tests."""

    def test_default_values(self) -> None:
        """Default settings have sensible values."""
        s = MachineSettings()
        assert s.max_power == 1000
        assert s.max_speed == 6000
        assert s.debug_level == DebugLevel.OFF

    def test_clamp_power_over_max(self) -> None:
        """Power above max is clamped."""
        s = MachineSettings(max_power=500)
        assert s.clamp_power(800) == 500

    def test_clamp_power_under_zero(self) -> None:
        """Negative power is clamped to zero."""
        s = MachineSettings()
        assert s.clamp_power(-50) == 0

    def test_clamp_speed(self) -> None:
        """Speed above max is clamped."""
        s = MachineSettings(max_speed=3000)
        assert s.clamp_speed(5000) == 3000


class TestMachineSettingsPersistence:
    """INI file round-trip tests."""

    def test_round_trip(self) -> None:
        """Settings survive save→load cycle."""
        with tempfile.NamedTemporaryFile(suffix=".ini", delete=False) as f:
            path = f.name

        try:
            settings = MachineSettings(
                max_power=800,
                max_speed=4000,
                travel_speed=3000,
                resolution=0.05,
                kerf_width=0.1,
                laser_mode=True,
                debug_level=DebugLevel.VERBOSE,
                path_optimization=False,
                direction_optimization=False,
                autolaunch=True,
            )
            save_machine_settings(settings, path=path)
            loaded = load_machine_settings(path=path)

            assert loaded.max_power == 800
            assert loaded.max_speed == 4000
            assert loaded.travel_speed == 3000
            assert loaded.resolution == pytest.approx(0.05)
            assert loaded.kerf_width == pytest.approx(0.1)
            assert loaded.laser_mode is True
            assert loaded.debug_level == DebugLevel.VERBOSE
            assert loaded.path_optimization is False
            assert loaded.direction_optimization is False
            assert loaded.autolaunch is True
        finally:
            os.unlink(path)

    def test_missing_file_returns_defaults(self) -> None:
        """Missing INI file produces default settings."""
        settings = load_machine_settings(path="/nonexistent/path.ini")
        assert settings.max_power == 1000
