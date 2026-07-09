"""Tests for _split_indices_from_connected_parameter_definition function."""

import pytest
import openmdao.api as om

from h2integrate.core.h2integrate_model import H2IntegrateModel


class TestSplitIndicesFromConnectedParameterDefinition:
    """Test suite for _split_indices_from_connected_parameter_definition method."""

    @staticmethod
    def split_indices(connected_parameter):
        """Helper to call the static method."""
        return H2IntegrateModel._split_indices_from_connected_parameter_definition(
            connected_parameter
        )

    @pytest.mark.unit
    def test_no_slices(self):
        """Test with parameter names that have no slice patterns."""
        params, src_indices = self.split_indices(["power_out", "power_in"])
        assert params == ["power_out", "power_in"]
        assert src_indices is None

    @pytest.mark.unit
    def test_source_slice_only(self):
        """Test with slice pattern only in source parameter."""
        params, src_indices = self.split_indices(["power_out[0:100]", "power_in"])
        assert params == ["power_out", "power_in"]
        assert src_indices == om.slicer[0:100]

    @pytest.mark.unit
    def test_dest_slice_only(self):
        """Test with slice pattern only in destination parameter."""
        params, src_indices = self.split_indices(["power_out", "power_in[0:8760]"])
        assert params == ["power_out", "power_in"]
        assert src_indices is None

    @pytest.mark.unit
    def test_both_slices(self):
        """Test with slice patterns in both parameters."""
        params, src_indices = self.split_indices(["power_out[0]", "power_in[0:8760]"])
        assert params == ["power_out", "power_in"]
        assert src_indices == om.slicer[[0] * 8760]

    @pytest.mark.unit
    def test_both_slices_tiled(self):
        """Test with slice patterns in both parameters."""
        params, src_indices = self.split_indices(["power_out[0,1]", "power_in[0:8760]"])
        assert params == ["power_out", "power_in"]
        assert src_indices == om.slicer[[0, 1] * 4380]

    @pytest.mark.unit
    def test_dest_partial_slice(self):
        """Test that a non-zero destination slice start raises a ValueError."""
        error_msg = "A non-zero start was provided for the slice for destination parameter"
        with pytest.raises(ValueError, match=error_msg):
            self.split_indices(["power_out[0]", "power_in[2:8760]"])

    @pytest.mark.unit
    def test_full_range_source_slice(self):
        """Test extraction of full range slices like [:]."""
        params, src_indices = self.split_indices(["source[:]", "dest"])
        assert params == ["source", "dest"]
        assert src_indices == om.slicer[:]

    @pytest.mark.unit
    def test_stepped_range_source_slice(self):
        """Test extraction of stepped slices like [0:100:2]."""
        params, src_indices = self.split_indices(["source[0:100:2]", "dest"])
        assert params == ["source", "dest"]
        assert src_indices == om.slicer[0:100:2]
