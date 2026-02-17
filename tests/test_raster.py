"""Tests for raster power interpolation."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

try:
    from raster.processor import RasterProcessor
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


@pytest.mark.skipif(not HAS_PIL, reason="Pillow not available")
class TestRasterPowerInterpolation:
    """Raster grayscale → power mapping tests."""

    def _setup_processor(self) -> RasterProcessor:
        """Create a processor for testing."""
        return RasterProcessor(dpi=100, direction="horizontal")

    def test_black_pixel_max_power(self) -> None:
        """Black pixel (0) maps to power_max."""
        proc = self._setup_processor()
        power = proc._pixel_to_power(0, power_min=0, power_range=1000)
        assert power == 1000

    def test_white_pixel_min_power(self) -> None:
        """White pixel (255) maps to power_min."""
        proc = self._setup_processor()
        power = proc._pixel_to_power(255, power_min=0, power_range=1000)
        assert power == 0

    def test_mid_gray_half_power(self) -> None:
        """Mid-gray pixel maps to approximately half power."""
        proc = self._setup_processor()
        power = proc._pixel_to_power(128, power_min=0, power_range=1000)
        assert 490 <= power <= 510  # ~50%

    def test_power_with_min_offset(self) -> None:
        """Power interpolation with non-zero power_min."""
        proc = self._setup_processor()
        power = proc._pixel_to_power(0, power_min=100, power_range=900)
        assert power == 1000

    def test_power_range(self) -> None:
        """Power values span the full range from min to max."""
        proc = self._setup_processor()
        p_min = proc._pixel_to_power(255, power_min=200, power_range=600)
        p_max = proc._pixel_to_power(0, power_min=200, power_range=600)
        assert p_min == 200
        assert p_max == 800

    def test_mono_gradient(self) -> None:
        """Monotonic: darker pixels get more power."""
        proc = self._setup_processor()
        powers = [
            proc._pixel_to_power(v, power_min=0, power_range=1000)
            for v in range(255, -1, -1)
        ]
        for i in range(len(powers) - 1):
            assert powers[i] <= powers[i + 1]
