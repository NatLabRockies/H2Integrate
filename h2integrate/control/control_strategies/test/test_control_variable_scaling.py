import pytest
import openmdao.api as om

from h2integrate.control.control_strategies.passthrough_controller import PassthroughController
from h2integrate.control.control_strategies.openloop_control_baseclass import (
    get_control_rate_reference,
)
from h2integrate.control.control_strategies.system_level.solver_options import (
    SLCSolverOptionsConfig,
)


@pytest.mark.unit
def test_get_control_rate_reference(subtests):
    with subtests.test("units take precedence over commodity"):
        assert get_control_rate_reference("hydrogen", "kW") == 1e5
        assert get_control_rate_reference("electricity", "kg/h") == 1e3

    with subtests.test("commodity fallback for other units"):
        assert get_control_rate_reference("electricity", None) == 1e5
        assert get_control_rate_reference("hydrogen", "kg/s") == 1e3
        assert get_control_rate_reference("ammonia", None) == 4e3

    with subtests.test("unknown commodity is unscaled"):
        assert get_control_rate_reference("unknown", None) == 1.0


@pytest.mark.unit
def test_solver_options_scale_control_variables(subtests):
    with subtests.test("default is off"):
        assert SLCSolverOptionsConfig().scale_control_variables is False

    with subtests.test("flag is not passed to the OpenMDAO solver"):
        options = SLCSolverOptionsConfig(scale_control_variables=True).get_solver_options()
        assert "scale_control_variables" not in options


@pytest.mark.unit
@pytest.mark.parametrize("scale_output", [True, False])
def test_passthrough_controller_scaling(subtests, scale_output):
    prob = om.Problem()
    prob.model.add_subsystem(
        "controller",
        PassthroughController(
            commodity="hydrogen",
            n_timesteps=4,
            commodity_rate_units="kg/h",
            scale_output=scale_output,
        ),
    )
    prob.setup()
    controller = prob.model.controller
    metadata = controller._var_rel2meta["hydrogen_command_value"]

    with subtests.test("command value reference scale"):
        if scale_output:
            assert metadata["ref"] == 1e3
            assert metadata["res_ref"] == 1e3
        else:
            assert metadata["ref"] == 1.0
            assert metadata["res_ref"] == 1.0

    with subtests.test("command value initial value"):
        assert metadata["val"].max() == (1.0 if scale_output else 1.0e9)

    with subtests.test("set point passes through unchanged"):
        prob.set_val("controller.hydrogen_set_point", [1.0, 2.0, 3.0, 4.0], units="kg/h")
        prob.run_model()
        assert prob.get_val("controller.hydrogen_command_value").tolist() == [1.0, 2.0, 3.0, 4.0]
