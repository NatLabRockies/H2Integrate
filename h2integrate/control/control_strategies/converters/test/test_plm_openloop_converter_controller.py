from types import SimpleNamespace

import numpy as np
import pytest
import openmdao.api as om

from h2integrate.converters.hydrogen.h2_fuel_cell import LinearH2FuelCellPerformanceModel
from h2integrate.control.control_strategies.converters.plm_openloop_converter_controller import (
    PLMHeuristicOpenLoopConverterController,
)


def _controller_without_setup(config, n_timesteps):
    controller = object.__new__(PLMHeuristicOpenLoopConverterController)
    controller.config = config
    controller.n_timesteps = n_timesteps
    return controller


@pytest.mark.unit
def test_plm_converter_controller_bounds_indicators():
    assert PLMHeuristicOpenLoopConverterController._time_step_bounds == (
        1e-12,
        np.inf,
    )


@pytest.mark.unit
def test_compute_electricity_upstream_dispatch_expected_profile():
    config = SimpleNamespace(
        commodity="hydrogen",
        demand_profile_peak_cutoff=90.0,
        demand_profile_upstream=[40.0, 80.0, 140.0, 110.0, 70.0],
        demand_profile_upstream_kind="commodity",
    )
    controller = _controller_without_setup(config, n_timesteps=5)

    inputs = {
        "hydrogen_set_point": np.array([50.0, 120.0, 100.0, 60.0, 80.0]),
        "rated_hydrogen_production": np.array([25.0]),
        "demand_profile_upstream_peak_cutoff": np.array([100.0]),
    }
    outputs = {}

    controller.compute(inputs, outputs)

    expected = np.array([0.0, 25.0, 25.0, 10.0, 0.0])
    np.testing.assert_allclose(outputs["hydrogen_command_value"], expected, rtol=1e-9)


@pytest.mark.unit
def test_compute_price_upstream_requires_price_trigger():
    """
    when the price is above the cutoff, then the lesser of the rated production
    and the desired dispatch (hydrogen_set_point - demand_profile_peak_cutoff)
    should be dispatched.
    """

    config = SimpleNamespace(
        commodity="hydrogen",
        demand_profile_peak_cutoff=90.0,
        demand_profile_upstream=[50.0, 120.0, 80.0],
        demand_profile_upstream_kind="price",
    )
    controller = _controller_without_setup(config, n_timesteps=3)

    inputs = {
        "hydrogen_set_point": np.array([120.0, 120.0, 80.0]),
        "rated_hydrogen_production": np.array([50.0]),
        "demand_profile_upstream_peak_cutoff": np.array([100.0]),
    }
    outputs = {}

    controller.compute(inputs, outputs)

    expected = np.array([0.0, 30.0, 0.0])
    np.testing.assert_allclose(outputs["hydrogen_command_value"], expected, rtol=1e-9)


@pytest.mark.unit
def test_compute_invalid_upstream_kind_raises():
    config = SimpleNamespace(
        commodity="hydrogen",
        demand_profile_peak_cutoff=90.0,
        demand_profile_upstream=[200.0],
        demand_profile_upstream_kind="invalid",
    )
    controller = _controller_without_setup(config, n_timesteps=1)

    inputs = {
        "hydrogen_set_point": np.array([100.0]),
        "rated_hydrogen_production": np.array([10.0]),
        "demand_profile_upstream_peak_cutoff": np.array([100.0]),
    }
    outputs = {}

    with pytest.raises(ValueError, match="Invalid demand_profile_upstream_kind"):
        controller.compute(inputs, outputs)


@pytest.mark.unit
def test_setup_uses_price_units_for_upstream_peak_cutoff():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 4,
                "dt": 3600,
            },
        }
    }
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "commodity": "hydrogen",
                "commodity_rate_units": "kg/h",
                "commodity_amount_units": "kg",
                "demand_profile": [10.0, 10.0, 10.0, 10.0],
                "demand_profile_peak_cutoff": 8.0,
                "demand_profile_upstream": [90.0, 110.0, 95.0, 105.0],
                "demand_profile_upstream_peak_cutoff": 100.0,
                "demand_profile_upstream_kind": "price",
            }
        }
    }

    prob = om.Problem()
    prob.model.add_subsystem(
        "controller",
        PLMHeuristicOpenLoopConverterController(
            plant_config=plant_config,
            tech_config=tech_config,
        ),
    )
    prob.setup()

    metadata = prob.model.get_io_metadata(iotypes="input")
    assert metadata["controller.demand_profile_upstream_peak_cutoff"]["units"] == "USD/kg"


@pytest.mark.integration
def test_plm_converter_controller_integrates_with_h2_fuel_cell(subtests):
    n_timesteps = 5

    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": n_timesteps,
                "dt": 3600,
            },
        }
    }

    control_tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "commodity": "electricity",
                "commodity_rate_units": "kW",
                "commodity_amount_units": "kW*h",
                "demand_profile": [50.0, 120.0, 100.0, 60.0, 80.0],
                "demand_profile_peak_cutoff": 90.0,
                "demand_profile_upstream": [40.0, 80.0, 140.0, 110.0, 70.0],
                "demand_profile_upstream_peak_cutoff": 100.0,
                "demand_profile_upstream_kind": "commodity",
            }
        }
    }

    fuel_cell_tech_config = {
        "model_inputs": {
            "performance_parameters": {
                "system_capacity_kw": 25.0,
                "fuel_cell_efficiency_hhv": 0.50,
                "uptime_hours_until_eol": 100,
            }
        }
    }

    prob = om.Problem()

    prob.model.add_subsystem(
        "ivc",
        om.IndepVarComp(),
        promotes=["*"],
    )
    prob.model.ivc.add_output(
        "electricity_in",
        val=np.zeros(n_timesteps),
        units="kW",
    )
    prob.model.ivc.add_output(
        "hydrogen_in",
        val=np.full(n_timesteps, 500.0),
        units="kg/h",
    )

    prob.model.add_subsystem(
        "controller",
        PLMHeuristicOpenLoopConverterController(
            plant_config=plant_config,
            tech_config=control_tech_config,
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "fuel_cell",
        LinearH2FuelCellPerformanceModel(
            plant_config=plant_config,
            tech_config=fuel_cell_tech_config,
            driver_config={},
        ),
        promotes=["*"],
    )

    prob.model.nonlinear_solver = om.NonlinearBlockGS(maxiter=20)

    prob.setup()
    prob.run_model()

    command = prob.get_val("electricity_command_value", units="kW")
    electricity_out = prob.get_val("electricity_out", units="kW")
    rated_production = prob.get_val("rated_electricity_production", units="kW")

    expected_command = np.array([0.0, 25.0, 25.0, 10.0, 0.0])
    expected_electricity_out = expected_command

    with subtests.test("controller outputs expected command profile"):
        np.testing.assert_allclose(command, expected_command, rtol=1e-9)

    with subtests.test("fuel cell output tracks controller command"):
        np.testing.assert_allclose(electricity_out, expected_electricity_out, rtol=1e-9)

    with subtests.test("controller reads rated production from fuel cell"):
        assert rated_production[0] == pytest.approx(25.0)
