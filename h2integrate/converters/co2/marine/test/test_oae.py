import numpy as np
import pytest
import openmdao.api as om
from openmdao.utils.assert_utils import assert_near_equal

from h2integrate.converters.co2.marine.ocean_alkalinity_enhancement import (
    OAECostModel,
    OAEPerformanceModel,
    OAECostAndFinancialModel,
)


# Representative performance outputs, so the cost models can be tested without the slow
# chemistry model
OAE_COST_INPUTS = {
    "annual_co2_produced": (9708.0, "t/year"),
    "mass_sellable_product": (5000.0, "t/year"),
    "value_products": (0.0, "USD/year"),
    "mass_acid_disposed": (0.0, "t/year"),
    "cost_acid_disposal": (0.0, "USD/year"),
    "based_added_seawater_max_power": (3.0e8, "mol/year"),
    "mass_rca": (1.0e7, "g"),
}


def run_oae_cost_model(model_class, plant_config, driver_config, **extra_inputs):
    prob = om.Problem()
    prob.model.add_subsystem(
        "cost",
        model_class(
            plant_config=plant_config,
            tech_config={"model_inputs": {}},
            driver_config=driver_config,
        ),
        promotes=["*"],
    )
    prob.setup()
    for name, (val, units) in {**OAE_COST_INPUTS, **extra_inputs}.items():
        prob.set_val(name, val, units=units)
    prob.run_model()
    return prob


@pytest.fixture(scope="module")
def tech_config():
    return {
        "model_inputs": {
            "performance_parameters": {
                "number_ed_min": 1,
                "number_ed_max": 5,
                "max_ed_system_flow_rate_m3s": 0.0324,  # m^3/s
                "frac_base_flow": 0.5,
                "assumed_CDR_rate": 0.8,  # mol CO2/mol NaOH
                "use_storage_tanks": True,
                "initial_tank_volume_m3": 0.0,  # m^3
                "store_hours": 12.0,  # hours
                "acid_disposal_method": "sell rca",
                "initial_salinity_ppt": 73.76,  # ppt
                "initial_temp_C": 10.0,  # degrees Celsius
                "initial_dic_mol_per_L": 0.0044,  # mol/L
                "initial_pH": 8.1,  # initial pH
            },
        },
    }


@pytest.fixture(scope="module")
def prob(tech_config, tmp_path_factory):
    """Run the OAE model once and share it, since the chemistry model is slow."""
    plant_config = {"plant": {"plant_life": 30, "simulation": {"n_timesteps": 8760, "dt": 3600}}}
    driver_config = {"general": {"folder_output": str(tmp_path_factory.mktemp("oae"))}}
    oae_model = OAEPerformanceModel(
        driver_config=driver_config, plant_config=plant_config, tech_config=tech_config
    )
    prob = om.Problem(model=om.Group())
    prob.model.add_subsystem("comp", oae_model, promotes=["*"])
    prob.setup()

    rng = np.random.default_rng(seed=42)
    base_power = np.linspace(3.0e8, 2.0e8, 8760)  # 300 MW to 200 MW over 8760 hours
    noise = rng.normal(loc=0, scale=0.5e8, size=8760)  # ±50 MW noise
    power_profile = base_power + noise
    prob.set_val("comp.electricity_in", power_profile, units="W")

    # Run the model
    prob.run_model()
    return prob


@pytest.mark.unit
def test_oae_outputs(prob, plant_config, subtests):
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    commodity = "co2"
    commodity_amount_units = "kg"
    commodity_rate_units = "kg/h"

    # Check that replacement schedule is between 0 and 1
    with subtests.test("0 <= replacement_schedule <=1"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("comp.replacement_schedule", units="unitless")) == plant_life

    # Check that capacity factor is between 0 and 1 with units of "unitless"
    with subtests.test("0 <= capacity_factor (unitless) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") <= 1)

    # Check that capacity factor is between 1 and 100 with units of "percent"
    with subtests.test("1 <= capacity_factor (percent) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") >= 1)
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") <= 100)

    with subtests.test("capacity_factor length"):
        assert len(prob.get_val("comp.capacity_factor", units="unitless")) == plant_life

    # Test that rated commodity production is greater than zero
    with subtests.test(f"rated_{commodity}_production > 0"):
        assert np.all(
            prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units) > 0
        )

    with subtests.test(f"rated_{commodity}_production length"):
        assert (
            len(prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units)) == 1
        )

    # Test that total commodity production is greater than zero
    with subtests.test(f"total_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units) > 0
        )
    with subtests.test(f"total_{commodity}_produced length"):
        assert (
            len(prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units)) == 1
        )

    # Test that annual commodity production is greater than zero
    with subtests.test(f"annual_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr")
            > 0
        )

    with subtests.test(f"annual_{commodity}_produced[1:] == annual_{commodity}_produced[0]"):
        annual_production = prob.get_val(
            f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
        )
        assert np.all(annual_production[1:] == annual_production[0])

    with subtests.test(f"annual_{commodity}_produced length"):
        assert len(annual_production) == plant_life

    # Test that commodity output has some values greater than zero
    with subtests.test(f"Some of {commodity}_out > 0"):
        assert np.any(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units) > 0)

    with subtests.test(f"{commodity}_out length"):
        assert len(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units)) == n_timesteps

    # Test default values
    with subtests.test("operational_life default value"):
        assert prob.get_val("comp.operational_life", units="yr") == plant_life
    with subtests.test("replacement_schedule value"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


@pytest.mark.regression
def test_oae_standard_outputs(prob, subtests):
    annual_co2_from_cf_calc = (
        prob.get_val("comp.capacity_factor", units="unitless")
        * prob.get_val("comp.rated_co2_production", units="t/h")
        * 8760
    )

    with subtests.test("CF calculated properly"):
        assert (
            pytest.approx(annual_co2_from_cf_calc[0], rel=1e-6)
            == prob.get_val("comp.annual_co2_produced", units="t/yr")[0]
        )


@pytest.mark.regression
def test_performance_model(prob):
    # Get output values to determine expected values
    co2_out = prob.get_val("co2_out", units="kg/h")
    co2_capture_mtpy = prob.get_val("annual_co2_produced", units="t/year")
    plant_mCC_capacity_mtph = prob.get_val("rated_co2_production", units="t/h")
    alkaline_seawater_flow_rate = prob.get_val("alkaline_seawater_flow_rate", units="m**3/s")
    alkaline_seawater_pH = prob.get_val("alkaline_seawater_pH", units="unitless")
    excess_acid = prob.get_val("excess_acid", units="m**3")

    # Assert values (allowing for small numerical tolerance)
    assert_near_equal(np.mean(co2_out), 1108.2428485572184, tolerance=1e-3)
    assert_near_equal(co2_capture_mtpy[0], [9708.207353361895], tolerance=1e-6)
    assert_near_equal(plant_mCC_capacity_mtph, [1.108546559943504], tolerance=1e-6)
    assert_near_equal(np.mean(alkaline_seawater_flow_rate), 3.2391123287671224, tolerance=1e-6)
    assert_near_equal(np.mean(alkaline_seawater_pH), 9.145157555568296, tolerance=1e-6)
    assert_near_equal(np.mean(excess_acid), 58.32, tolerance=1e-6)


@pytest.mark.unit
def test_oae_cost_model(plant_config, driver_config, subtests):
    prob = run_oae_cost_model(OAECostModel, plant_config, driver_config)

    with subtests.test("CapEx and OpEx are positive"):
        assert prob.get_val("CapEx", units="USD")[0] > 0
        assert prob.get_val("OpEx", units="USD/year")[0] > 0

    with subtests.test("cost_year"):
        assert prob.get_val("cost_year") == 2024


@pytest.mark.unit
def test_oae_cost_and_financial_model_energy_cost(plant_config, driver_config, subtests):
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
    annual_input_electricity = 1.0e9  # kWh/year
    unused_power = 1.0e3  # kW in every hour
    lcoe = 0.05  # USD/kWh
    energy_inputs = {
        "annual_input_electricity": (annual_input_electricity, "kW*h/year"),
        "unused_energy": (np.full(n_timesteps, unused_power), "kW"),
    }

    cost_only = run_oae_cost_model(OAECostModel, plant_config, driver_config)
    free_energy = run_oae_cost_model(
        OAECostAndFinancialModel,
        plant_config,
        driver_config,
        LCOE=(0.0, "USD/(kW*h)"),
        **energy_inputs,
    )
    paid_energy = run_oae_cost_model(
        OAECostAndFinancialModel,
        plant_config,
        driver_config,
        LCOE=(lcoe, "USD/(kW*h)"),
        **energy_inputs,
    )

    with subtests.test("Matches OAECostModel when energy is free"):
        assert free_energy.get_val("CapEx", units="USD") == pytest.approx(
            cost_only.get_val("CapEx", units="USD"), rel=1e-12
        )
        assert free_energy.get_val("OpEx", units="USD/year") == pytest.approx(
            cost_only.get_val("OpEx", units="USD/year"), rel=1e-12
        )

    with subtests.test("OpEx includes the cost of the electricity actually used"):
        used_electricity = annual_input_electricity - unused_power * n_timesteps
        opex_increase = paid_energy.get_val("OpEx", units="USD/year") - free_energy.get_val(
            "OpEx", units="USD/year"
        )
        assert opex_increase == pytest.approx(lcoe * used_electricity, rel=1e-9)

    with subtests.test("Carbon credit value gives zero NPV"):
        assert free_energy.get_val("NPV", units="USD")[0] == pytest.approx(0.0, abs=1.0)
        assert paid_energy.get_val("NPV", units="USD")[0] == pytest.approx(0.0, abs=1.0)

    with subtests.test("Energy cost raises the required carbon credit"):
        assert paid_energy.get_val("carbon_credit_value", units="USD/t") > free_energy.get_val(
            "carbon_credit_value", units="USD/t"
        )


@pytest.mark.unit
def test_oae_cost_and_financial_model_requires_electricity(plant_config, driver_config):
    with pytest.raises(AttributeError, match="annual_input_electricity needs to be connected"):
        run_oae_cost_model(OAECostAndFinancialModel, plant_config, driver_config)


@pytest.mark.regression
def test_oae_cost_model_values(plant_config, driver_config, subtests):
    prob = run_oae_cost_model(OAECostModel, plant_config, driver_config)
    with subtests.test("CapEx"):
        assert prob.get_val("CapEx", units="USD")[0] == pytest.approx(10367737.167808551, rel=1e-6)
    with subtests.test("OpEx"):
        assert prob.get_val("OpEx", units="USD/year")[0] == pytest.approx(
            1302278.7821029117, rel=1e-6
        )


@pytest.mark.regression
def test_oae_cost_model_from_performance_outputs(prob, plant_config, driver_config, subtests):
    units = {name: u for name, (_, u) in OAE_COST_INPUTS.items()}
    perf_outputs = {name: (prob.get_val(name, units=u), u) for name, u in units.items()}
    cost = run_oae_cost_model(OAECostModel, plant_config, driver_config, **perf_outputs)
    with subtests.test("CapEx"):
        assert cost.get_val("CapEx", units="USD")[0] == pytest.approx(10081969.902826248, rel=1e-6)
    with subtests.test("OpEx"):
        assert cost.get_val("OpEx", units="USD/year")[0] == pytest.approx(
            1266383.905546671, rel=1e-6
        )


@pytest.mark.regression
@pytest.mark.parametrize(
    "lcoe,capex,opex,carbon_credit",
    [
        (0.0, 10367737.167808551, 1302278.7821029117, 217.66508529363426), # free energy scenario
        (0.05, 59929737.167808555, 50864278.78210291, 5803.756528678582), # paid energy scenario
    ],
)
def test_oae_cost_and_financial_model_values(
    plant_config, driver_config, subtests, lcoe, capex, opex, carbon_credit
):
    prob = run_oae_cost_model(
        OAECostAndFinancialModel,
        plant_config,
        driver_config,
        LCOE=(lcoe, "USD/(kW*h)"),
        annual_input_electricity=(1.0e9, "kW*h/year"),
        unused_energy=(np.full(8760, 1.0e3), "kW"),
    )
    with subtests.test("CapEx (includes one year of energy cost as working capital)"):
        assert prob.get_val("CapEx", units="USD")[0] == pytest.approx(capex, rel=1e-6)
    with subtests.test("OpEx"):
        assert prob.get_val("OpEx", units="USD/year")[0] == pytest.approx(opex, rel=1e-6)
    with subtests.test("carbon_credit_value"):
        assert prob.get_val("carbon_credit_value", units="USD/t")[0] == pytest.approx(
            carbon_credit, rel=1e-6
        )
