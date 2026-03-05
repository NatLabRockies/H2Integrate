import pytest
import openmdao.api as om
from pytest import approx

from h2integrate.transporters.pipe import PipePerformanceModel


@pytest.mark.unit
def test_pipe_with_hydrogen():
    """Test the pipe transport with hydrogen as transport_item."""

    # Create the pipe component with hydrogen as transport item
    pipe = PipePerformanceModel(transport_item="hydrogen")

    # Create OpenMDAO problem and add the component
    prob = om.Problem()
    prob.model.add_subsystem("pipe", pipe, promotes=["*"])

    # Add independent variable component for input
    ivc = om.IndepVarComp()
    ivc.add_output("hydrogen_in", val=10.0, units="kg/s")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    # Setup and run the model
    prob.setup()
    prob.set_val("hydrogen_in", 10.0, units="kg/s")
    prob.run_model()

    # Check that output equals input (pass-through pipe with no losses)
    hydrogen_in = prob.get_val("hydrogen_in", units="kg/s")
    hydrogen_out = prob.get_val("hydrogen_out", units="kg/s")

    assert hydrogen_out == approx(hydrogen_in, rel=1e-10)
    assert hydrogen_out == approx(10.0, rel=1e-10)


@pytest.mark.unit
def test_pipe_with_invalid_transport_item():
    """Test that pipe raises an error with invalid transport_item."""
    with pytest.raises(ValueError) as excinfo:
        PipePerformanceModel(transport_item="invalid_item")
    assert "Value ('invalid_item')" in str(excinfo.value)
