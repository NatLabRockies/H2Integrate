import numpy as np
import pytest
import openmdao.api as om

from h2integrate.storage.generic_storage_cost import GenericStorageCostModel


@pytest.fixture
def plant_config():
    return {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 24, "dt": 3600}}}


@pytest.fixture
def battery_tech_config():
    return {
        "model_inputs": {
            "shared_parameters": {
                "commodity_rate_units": "kW",
                "max_charge_rate": 20000.0,  # kW
                "max_capacity": 80000.0,  # kWh, 4-hour duration
            },
            "cost_parameters": {
                "cost_year": 2022,
                "capacity_capex": 310.0,  # USD/kWh
                "charge_capex": 311.0,  # USD/kW
                "opex_fraction": 0.025,
            },
        }
    }


def run_cost_model(plant_config, tech_config, **values):
    prob = om.Problem()
    comp = GenericStorageCostModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    for name, value in values.items():
        prob.set_val(name, value)
    prob.run_model()
    return prob


@pytest.mark.unit
def test_generic_storage_cost_battery(subtests, plant_config, battery_tech_config):
    prob = run_cost_model(plant_config, battery_tech_config)
    expected_capex = (4 * 310.0 + 311.0) * 20000.0

    with subtests.test("CapEx combines capacity and charge rate costs"):
        assert prob.get_val("CapEx", units="USD") == pytest.approx(expected_capex)

    with subtests.test("OpEx is a fraction of CapEx"):
        assert prob.get_val("OpEx", units="USD/year") == pytest.approx(0.025 * expected_capex)

    with subtests.test("Cost year"):
        assert prob.get_val("cost_year") == 2022


@pytest.mark.unit
def test_generic_storage_cost_unit_conversion(plant_config, battery_tech_config):
    # The same battery described in MW and MWh costs the same
    battery_tech_config["model_inputs"]["shared_parameters"].update(
        {"commodity_rate_units": "MW", "max_charge_rate": 20.0, "max_capacity": 80.0}
    )
    battery_tech_config["model_inputs"]["cost_parameters"].update(
        {"capacity_capex": 310.0e3, "charge_capex": 311.0e3}
    )
    prob = run_cost_model(plant_config, battery_tech_config)

    assert prob.get_val("CapEx", units="USD") == pytest.approx((4 * 310.0 + 311.0) * 20000.0)


@pytest.mark.unit
def test_generic_storage_cost_mass_commodity(subtests, plant_config):
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "commodity_rate_units": "kg/h",
                "commodity_amount_units": "kg",
                "max_charge_rate": 100.0,  # kg/h
                "max_capacity": 1000.0,  # kg, 10-hour duration
            },
            "cost_parameters": {
                "cost_year": 2022,
                "capacity_capex": 500.0,  # USD/kg
                "charge_capex": 1000.0,  # USD/(kg/h)
                "opex_fraction": 0.01,
            },
        }
    }
    prob = run_cost_model(plant_config, tech_config)
    expected_capex = (10 * 500.0 + 1000.0) * 100.0

    with subtests.test("CapEx"):
        assert prob.get_val("CapEx", units="USD") == pytest.approx(expected_capex)

    with subtests.test("Storage size inputs can be overridden"):
        prob.set_val("storage_capacity", 2000.0, units="kg")
        prob.run_model()
        assert prob.get_val("CapEx", units="USD") == pytest.approx((20 * 500.0 + 1000.0) * 100.0)


@pytest.mark.unit
def test_generic_storage_cost_zero_charge_rate(plant_config, battery_tech_config):
    prob = run_cost_model(plant_config, battery_tech_config, max_charge_rate=0.0)

    assert prob.get_val("CapEx", units="USD") == pytest.approx(0.0)
    assert prob.get_val("OpEx", units="USD/year") == pytest.approx(0.0)


@pytest.mark.unit
def test_generic_storage_cost_negative_charge_rate(plant_config, battery_tech_config):
    with pytest.raises(UserWarning, match="max_charge_rate cannot be less than zero"):
        run_cost_model(plant_config, battery_tech_config, max_charge_rate=-1.0)


@pytest.mark.unit
@pytest.mark.parametrize(
    "parameter,value",
    [("commodity_rate_units", "gal/h"), ("opex_fraction", 1.5), ("capacity_capex", -1.0)],
)
def test_generic_storage_cost_invalid_config(plant_config, battery_tech_config, parameter, value):
    battery_tech_config["model_inputs"]["shared_parameters"][parameter] = value

    with pytest.raises(ValueError, match=parameter):
        run_cost_model(plant_config, battery_tech_config)


@pytest.mark.unit
def test_generic_storage_cost_capex_is_linear_in_size(plant_config, battery_tech_config):
    sizes = np.array([10000.0, 20000.0, 40000.0])
    capex = [
        run_cost_model(
            plant_config,
            battery_tech_config,
            max_charge_rate=size,
            storage_capacity=4 * size,
        ).get_val("CapEx", units="USD")[0]
        for size in sizes
    ]

    np.testing.assert_allclose(capex, (4 * 310.0 + 311.0) * sizes)
