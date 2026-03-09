import numpy as np
import pytest
import openmdao.api as om

from h2integrate.core.supported_models import supported_models


@pytest.fixture
def tech_config(max_capacity, max_charge_rate):
    config = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": max_capacity,
                "max_charge_rate": max_charge_rate,
            }
        }
    }
    return config


# fmt: off
@pytest.mark.regression
@pytest.mark.parametrize(
    "model,n_timesteps,max_capacity,max_charge_rate,expected_capex,expected_opex,expected_var_opex,cost_year",
    [
        ("SaltCavernStorageCostModel", 8760, 3580383.39133725, 12549.62622698, 65337437.17944019, 3149096.037312646, 0, 2018),  # noqa: E501
        ("LinedRockCavernStorageCostModel", 8760, 169320.79994693, 1568.70894716, 18693728.23242369, 1099582.4333529277, 0, 2018),  # noqa: E501
        ("LinedRockCavernStorageCostModel", 8760, 2081385.93267781, 14118.14678877, 92392496.03198986, 4292680.718474801, 0, 2018),  # noqa: E501
        ("LinedRockCavernStorageCostModel", 8760, 2987042.0, 12446.00729773, 1.28437699 * 1e8, 5315184.827689768, 0, 2018),  # noqa: E501
        ("PipeStorageCostModel", 8760, 3580383.39133725, 12549.62622698, 1827170156.1390543, 57720829.60694359, 0, 2018),  # noqa: E501
        ("LinedRockCavernStorageCostModel", 8760, 1000000, 100000 / 24, 51136144, 2359700.44640052, 0, 2018),  # noqa: E501
        ("SaltCavernStorageCostModel", 8760, 1000000, 100000 / 24, 24992482.4198, 1461663.9089168755, 0, 2018),  # noqa: E501
        ("PipeStorageCostModel", 8760, 1000000, 100000 / 24, 508745483.851, 16439748.432128396, 0, 2018),  # noqa: E501
    ],
    ids=[
        "SaltCavernStorageCostModel-ex2",
        "LinedRockCavernStorageCostModel-ex12-small",
        "LinedRockCavernStorageCostModel-ex1",
        "LinedRockCavernStorageCostModel-ex14",
        "PipeStorageCostModel",
        "LinedRockCavernStorageCostModel-1M-kg",
        "SaltCavernStorageCostModel-1M-kg",
        "PipeStorageCostModel-1M-kg",
    ]
)
# fmt: on
def test_h2_storage_capex_opex(
    subtests,
    plant_config,
    tech_config,
    model,
    n_timesteps,
    max_charge_rate,
    expected_capex,
    expected_opex,
    expected_var_opex,
    cost_year,
):
    prob = om.Problem()
    comp = supported_models[model](
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()

    # Set hydrogen_in to a constant timeseries equal to max_charge_rate so that
    # the average flow rate equals the max charge rate (preserving regression values)
    prob.set_val("sys.hydrogen_in", np.full(n_timesteps, max_charge_rate), units="kg/h")

    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx", units="USD")[0], rel=1e-6) == expected_capex
    with subtests.test("OpEx"):
        assert pytest.approx(
            prob.get_val("sys.OpEx", units="USD/year")[0], rel=1e-6
        ) == expected_opex
    with subtests.test("VarOpEx"):
        assert (
            pytest.approx(np.sum(prob.get_val("sys.VarOpEx", units="USD/year")), rel=1e-6)
            == expected_var_opex
        )
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == cost_year


# fmt: off
@pytest.mark.regression
@pytest.mark.parametrize(
    "model,n_timesteps,max_capacity,max_charge_rate,a,b,c",
    [
        ("LinedRockCavernStorageCostModel", 8760, 1000000, 100000 / 24,  0.095803, 1.5868, 10.332),
        ("SaltCavernStorageCostModel", 8760, 1000000, 100000 / 24, 0.092548, 1.6432, 10.161),
        ("PipeStorageCostModel", 8760, 1000000, 100000 / 24, 0.0041617, 0.060369, 6.4581),
    ],
    ids=[
        "LinedRockCavernStorageCostModel-1M-kg",
        "SaltCavernStorageCostModel-1M-kg",
        "PipeStorageCostModel-1M-kg",
    ]
)
# fmt: on
def test_h2_storage_capex_per_kg(
    plant_config,
    tech_config,
    model,
    n_timesteps,
    max_capacity,
    max_charge_rate,
    a,
    b,
    c,
):
    """Test based on original test_lined_rock_storage.py with 1M kg storage capacity."""
    prob = om.Problem()
    comp = supported_models[model](
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()

    # Set hydrogen_in to a constant timeseries equal to max_charge_rate
    prob.set_val("sys.hydrogen_in", np.full(n_timesteps, max_charge_rate), units="kg/h")

    prob.run_model()

    # Calculate expected capex per kg
    h2_storage_kg = max_capacity
    capex_per_kg = np.exp(
        a * (np.log(h2_storage_kg / 1000)) ** 2 - b * np.log(h2_storage_kg / 1000) + c
    )
    cepci_overall = 1.29 / 1.30
    expected_capex = cepci_overall * capex_per_kg * h2_storage_kg

    assert pytest.approx(prob.get_val("sys.CapEx", units="USD")[0], rel=1e-6) == expected_capex


@pytest.mark.regression
def test_h2_storage_average_flow_rate():
    """Test that system_flow_rate uses the average of hydrogen_in, not the max charge rate.

    This test verifies the fix for the incorrect system sizing bug where
    the HDSAM-based cost models were using the maximum fill rate instead of
    the average system flow rate (per Papadias 2021 / HDSAM V4.0).

    We run the same model twice:
    1. With a constant hydrogen_in timeseries (mean == max)
    2. With a variable hydrogen_in timeseries (mean < max)

    The CapEx should be the same (depends on storage capacity, not flow rate),
    but the OpEx should differ because it depends on system_flow_rate (compressor
    sizing, labor, etc.).
    """
    n_timesteps = 8760
    max_capacity = 1000000  # kg
    max_charge_rate = 100000 / 24  # kg/h

    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {"dt": 3600, "n_timesteps": n_timesteps},
        },
    }
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": max_capacity,
                "max_charge_rate": max_charge_rate,
            }
        }
    }

    # Run 1: constant hydrogen_in = max_charge_rate (mean == max)
    prob1 = om.Problem()
    comp1 = supported_models["LinedRockCavernStorageCostModel"](
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
    )
    prob1.model.add_subsystem("sys", comp1)
    prob1.setup()
    prob1.set_val("sys.hydrogen_in", np.full(n_timesteps, max_charge_rate), units="kg/h")
    prob1.run_model()

    # Run 2: variable hydrogen_in with mean = max_charge_rate / 2
    # (half the time at max, half the time at zero)
    hydrogen_in_variable = np.zeros(n_timesteps)
    hydrogen_in_variable[: n_timesteps // 2] = max_charge_rate
    prob2 = om.Problem()
    comp2 = supported_models["LinedRockCavernStorageCostModel"](
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
    )
    prob2.model.add_subsystem("sys", comp2)
    prob2.setup()
    prob2.set_val("sys.hydrogen_in", hydrogen_in_variable, units="kg/h")
    prob2.run_model()

    capex1 = prob1.get_val("sys.CapEx", units="USD")[0]
    capex2 = prob2.get_val("sys.CapEx", units="USD")[0]
    opex1 = prob1.get_val("sys.OpEx", units="USD/year")[0]
    opex2 = prob2.get_val("sys.OpEx", units="USD/year")[0]

    # CapEx should be the same (depends on storage capacity, not flow rate)
    assert pytest.approx(capex1, rel=1e-6) == capex2

    # OpEx should be lower for the variable case (lower average flow rate)
    assert opex2 < opex1
