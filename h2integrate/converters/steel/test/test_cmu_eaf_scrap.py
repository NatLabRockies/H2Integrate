import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.steel.cmu_electric_arc_furnace_scrap import (
    CMUElectricArcFurnaceScrapOnlyPerformanceComponent,
)


@fixture
def steel_config():
    config = {
        "model_inputs": {
            "performance_parameters": {
                "steel_production_rate_tonnes_per_year": 1.00066324201,  # based on openmdao year
                "steel_percent_carbon": 0.001,
                "scrap_composition": {"Fe": 0.94, "SiO2": 0.01},
                "energy_mass_balance_dict": {
                    # MMBtu/ton steel, '5. Electric Arc Furnace!C32'
                    "natural_gas": 0.44,
                    # kg electrodes per ton steel, '5. Electric Arc Furnace!C33'
                    "electrodes": 2.00,
                    # basicity, kg CaO / (kg SiO2 + kg Al2O3), '12. EAF Mass & Energy Balance!D51'
                    "slag_basicity": 1.50,
                    # kg Al2O3 in slag per ton scrap, '12. EAF Mass & Energy Balance!D53'
                    "mass_Al2O3_slag_per_tscrap": 0.0,
                    # total kg Al2O3 in slag per ton LS, '12. EAF Mass & Energy Balance!D75'
                    "mass_Al2O3_slag_per_tLS": 0.0,
                    # mass fraction MgO in slag, assumed input, '12. EAF Mass & Energy Balance!D56'
                    "pct_MgO_slag": 12.0 / 100,
                    # mass fraction FeO in slag, assumed input, '12. EAF Mass & Energy Balance!D57'
                    "pct_FeO_slag": 30.0 / 100,
                    # mass fraction carbon input to EAF as % of steel tap mass,
                    # '12. EAF Mass & Energy Balance!D89'
                    "pct_carbon_steel_tap": 3 / 100,
                    # (kg/kg), '12. EAF Mass & Energy Balance!D113'
                    "CaO_MgO_ratio": 56.00 / 40.00,
                    # (kWh/tonne) assumption input on '5. Electric Arc Furnace'!C6
                    "electricity_kWh_per_tonne_steel": 470.0,
                },
            }
        }
    }
    return config


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
        "finance_parameters": {
            "cost_adjustment_parameters": {
                "cost_year_adjustment_inflation": 0.025,
                "target_dollar_year": 2022,
            }
        },
    }
    return plant_config


@fixture
def feedstock_availability_costs():
    feedstocks_dict = {
        "oxygen": {
            "rated_capacity": 500000.0,  # need
            "units": "m**3/h",
            "price": 0.15,  # USD/m**3
        },
        "electricity": {
            "rated_capacity": 500000000.0,  # need
            "units": "kW",
            "price": 0.083,  # USD/kWh
        },
        "natural_gas": {
            "rated_capacity": 10000000.0,  # need
            "units": "MMBtu/h",
            "price": 6.45,  # USD/MMBtu
        },
        "electrodes": {
            "rated_capacity": 2.0,  # need
            "units": "t/h",
            "price": 3.67,  # USD/kg
        },
        "scrap": {
            "rated_capacity": 100000000,  # need
            "units": "t/h",
            "price": 1.07,  # USD/t
        },
        "coal": {
            "rated_capacity": 10,  # need
            "units": "t/h",
            "price": 150.00,  # USD/t
        },
        "doloma": {
            "rated_capacity": 2.0,  # need
            "units": "t/h",
            "price": 3.67,  # USD/kg
        },
        "lime": {
            "rated_capacity": 2.0,  # need
            "units": "t/h",
            "price": 120.00,  # USD/t
        },
    }
    return feedstocks_dict


@pytest.mark.unit
def test_energy_mass_balance_per_unit(
    steel_config, plant_config, feedstock_availability_costs, subtests
):
    prob = om.Problem()

    perf = CMUElectricArcFurnaceScrapOnlyPerformanceComponent(
        plant_config=plant_config, tech_config=steel_config, driver_config={}
    )

    prob.model.add_subsystem("perf", perf, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )
    prob.run_model()

    with subtests.test("kg_slag"):
        assert pytest.approx(sum(prob.get_val("slag_out")), rel=1e-6) == 46.30399113656538

    with subtests.test("kg_MGO_in_slag"):
        assert pytest.approx(sum(prob.get_val("mass_MgO_slag")), rel=1e-6) == 5.556478936388529

    with subtests.test("kg_FeO_in_slag"):
        assert pytest.approx(sum(prob.get_val("mass_FeO_slag")), rel=1e-6) == 13.891197340972685

    with subtests.test("mass_Fe_from_scrap"):
        assert pytest.approx(sum(prob.get_val("mass_Fe_from_scrap")), rel=1e-6) == 999

    with subtests.test("mass_steel_per_unit_scrap"):
        assert (
            pytest.approx(prob.get_val("mass_steel_per_unit_scrap"), rel=1e-6) == 930.8794677884603
        )

    with subtests.test("oxygen_consumed"):
        assert pytest.approx(sum(prob.get_val("oxygen_consumed")), rel=1e-6) == 42.197236934381564

    with subtests.test("electricity_consumed"):
        assert pytest.approx(sum(prob.get_val("electricity_consumed")), rel=1e-6) == 470.0

    with subtests.test("natural_gas_consumed"):
        assert pytest.approx(sum(prob.get_val("natural_gas_consumed")), rel=1e-6) == 0.44

    with subtests.test("electrodes_consumed"):
        assert pytest.approx(sum(prob.get_val("electrodes_consumed")), rel=1e-6) == 2.0

    with subtests.test("scrap_consumed"):
        assert pytest.approx(sum(prob.get_val("scrap_consumed")), rel=1e-6) == 1.0742525943685

    with subtests.test("coal_consumed"):
        assert pytest.approx(sum(prob.get_val("coal_consumed")), rel=1e-6) == 0.03722084367245657

    with subtests.test("doloma_consumed"):
        assert pytest.approx(sum(prob.get_val("doloma_consumed")), rel=1e-6) == 0.013335549447331245

    with subtests.test("lime_consumed"):
        assert (
            pytest.approx(sum(prob.get_val("lime_consumed", units="t/h")), rel=1e-6)
            == 0.008334718404582999
        )


@pytest.mark.unit
def test_scrap_EAF_performance(steel_config, plant_config, feedstock_availability_costs, subtests):
    prob = om.Problem()

    perf = CMUElectricArcFurnaceScrapOnlyPerformanceComponent(
        plant_config=plant_config, tech_config=steel_config, driver_config={}
    )

    prob.model.add_subsystem("perf", perf, promotes=["*"])
    prob.setup()

    for feedstock_name, feedstock_info in feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )
    prob.run_model()

    with subtests.test("steel_out"):
        assert pytest.approx(sum(prob.get_val("steel_out")), rel=1e-6) == 0.9999999999999999

    with subtests.test("rated_steel_production"):
        assert (
            pytest.approx(prob.get_val("rated_steel_production", units="t/h"), rel=1e-6)
            == 0.000114155214
        )

    with subtests.test("total_steel_produced"):
        assert (
            pytest.approx(prob.get_val("total_steel_produced", units="t"), rel=1e-6) == 0.99999999
        )

    with subtests.test("annual_steel_produced"):
        assert (
            pytest.approx(prob.get_val("annual_steel_produced", units="t/yr"), rel=1e-6)
            == 0.9999999
        )

    with subtests.test("capacity_factor"):
        assert pytest.approx(prob.get_val("capacity_factor"), rel=1e-6) == 1.0


@pytest.mark.unit
def test_cmu_eaf_error(steel_config, plant_config, feedstock_availability_costs, subtests):
    prob = om.Problem()

    perf = CMUElectricArcFurnaceScrapOnlyPerformanceComponent(
        plant_config=plant_config, tech_config=steel_config, driver_config={}
    )

    prob.model.add_subsystem("perf", perf, promotes=["*"])
    prob.setup()

    prob.set_val("annual_production", 3000000, units="t/year")

    for feedstock_name, feedstock_info in feedstock_availability_costs.items():
        prob.set_val(
            f"perf.{feedstock_name}_in",
            feedstock_info["rated_capacity"],
            units=feedstock_info["units"],
        )

    with pytest.raises(
        ValueError, match="Rated steel production .* cannot exceed rated steel capacity .*"
    ):
        prob.run_model()
