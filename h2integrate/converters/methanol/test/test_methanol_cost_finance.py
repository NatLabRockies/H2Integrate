import numpy as np
import pytest
import openmdao.api as om
from openmdao.utils.units import convert_units

from h2integrate.converters.methanol.smr_methanol_plant import (
    SMRMethanolPlantCostModel,
    SMRMethanolPlantFinanceModel,
    SMRMethanolPlantPerformanceModel,
)
from h2integrate.converters.methanol.co2h_methanol_plant import (
    CO2HMethanolPlantCostModel,
    CO2HMethanolPlantFinanceModel,
)


N_TIMESTEPS = 8760
PLANT_CAPACITY_KGPY = 8760000.0  # 1000 kg/h of methanol at full capacity
METHANOL_RATE = 900.0  # kg/h
ANNUAL_METHANOL = METHANOL_RATE * N_TIMESTEPS
PPA_PRICE = 0.027498168  # USD/kWh
SHARED_PARAMETERS = {
    "plant_capacity_kgpy": PLANT_CAPACITY_KGPY,
    "plant_capacity_flow": "methanol",
}
FINANCE_PARAMETERS = {"tasc_toc_multiplier": 1.093, "fixed_charge_rate": 0.0707}
CO2H_COST_PARAMETERS = {
    "ng_lhv": 47.1,
    "toc_kg_y": 1.0633873,
    "foc_kg_y2": 0.020743864,
    "voc_kg": 0.00079,
    "meoh_syn_cat_price": 615.274273,
    "ng_price": 4.0,
    "co2_price": 0.0549007,
    "cost_year": 2020,
}
SMR_COST_PARAMETERS = {
    "ng_lhv": 47.1,
    "toc_kg_y": 0.782749307,
    "foc_kg_y2": 0.020675078,
    "voc_kg": 0.012271827,
    "meoh_syn_cat_price": 615.274273,
    "meoh_atr_cat_price": 747.9768786,
    "ng_price": 4.0,
    "cost_year": 2020,
}
SMR_PERFORMANCE_PARAMETERS = {
    "capacity_factor": 0.9,
    "co2e_emit_ratio": 1.13442,
    "h2o_consume_ratio": 2.669877132,
    "meoh_syn_cat_consume_ratio": 0.00000036322492251,
    "meoh_atr_cat_consume_ratio": 0.0000013078433938,
    "ng_consume_ratio": 0.7674355312,
    "elec_produce_ratio": 0.338415339,
}


@pytest.fixture
def plant_config():
    return {
        "plant": {
            "plant_life": 30,
            "ppa_price": PPA_PRICE,
            "simulation": {"n_timesteps": N_TIMESTEPS, "dt": 3600},
        }
    }


def run_components(components, plant_config, tech_config, **values):
    """Run components with all variables promoted, after setting the given input values."""
    prob = om.Problem()
    for name, component_class in components.items():
        comp = component_class(plant_config=plant_config, tech_config=tech_config, driver_config={})
        prob.model.add_subsystem(name, comp, promotes=["*"])
    prob.setup()
    for name, value in values.items():
        prob.set_val(name, value)
    prob.run_model()
    return prob


def hourly(value):
    return np.full(N_TIMESTEPS, value)


@pytest.mark.unit
def test_co2h_methanol_cost(subtests, plant_config):
    tech_config = {
        "model_inputs": {
            "shared_parameters": SHARED_PARAMETERS,
            "cost_parameters": CO2H_COST_PARAMETERS,
        }
    }
    prob = run_components(
        {"cost": CO2HMethanolPlantCostModel},
        plant_config,
        tech_config,
        methanol_out=hourly(METHANOL_RATE),
        meoh_syn_cat_consume=10.0,
        ng_consume=hourly(66.0),
        carbon_dioxide_consume=hourly(1280.0),
    )
    ng_lhv_mmbtu_per_kg = convert_units(47.1, "MJ", "MBtu")
    expected = {
        "Fixed_OpEx": PLANT_CAPACITY_KGPY * 0.020743864,
        "Variable_OpEx": ANNUAL_METHANOL * 0.00079,
        "meoh_syn_cat_cost": 10.0 * 615.274273,
        "ng_cost": 66.0 * N_TIMESTEPS * ng_lhv_mmbtu_per_kg * 4.0,
        "co2_cost": 1280.0 * N_TIMESTEPS * 0.0549007,
    }

    with subtests.test("CapEx is the total overnight cost"):
        assert prob.get_val("CapEx", units="USD") == pytest.approx(PLANT_CAPACITY_KGPY * 1.0633873)

    with subtests.test("Annual cost components"):
        for name, value in expected.items():
            assert prob.get_val(name, units="USD/year") == pytest.approx(value), name

    with subtests.test("OpEx is the sum of the annual cost components"):
        assert prob.get_val("OpEx", units="USD/year") == pytest.approx(sum(expected.values()))


@pytest.mark.unit
def test_co2h_methanol_finance(subtests, plant_config):
    tech_config = {
        "model_inputs": {
            "shared_parameters": SHARED_PARAMETERS,
            "finance_parameters": FINANCE_PARAMETERS,
        }
    }
    prob = run_components(
        {"finance": CO2HMethanolPlantFinanceModel},
        plant_config,
        tech_config,
        CapEx=1.0e7,
        Fixed_OpEx=2.0e5,
        Variable_OpEx=5.0e4,
        meoh_syn_cat_cost=6.0e3,
        ng_cost=3.0e4,
        co2_cost=4.0e4,
        methanol_out=hourly(METHANOL_RATE),
        electricity_consume=hourly(0.0947 * METHANOL_RATE),
        hydrogen_consume=hourly(0.195 * METHANOL_RATE),
        LCOE=0.05,
        LCOH=4.0,
    )
    expected = {
        "LCOM_meoh_capex": 1.0e7 * 0.0707 * 1.093 / ANNUAL_METHANOL,
        "LCOM_meoh_fopex": 2.0e5 / ANNUAL_METHANOL,
        "LCOM_meoh_syn_cat": 6.0e3 / ANNUAL_METHANOL,
        "LCOM_ng": 3.0e4 / ANNUAL_METHANOL,
        "LCOM_co2": 4.0e4 / ANNUAL_METHANOL,
        "LCOM_elec": 0.05 * 0.0947,
        "LCOM_h2": 4.0 * 0.195,
    }
    lcom_meoh = (1.0e7 * 0.0707 * 1.093 + 2.0e5 + 5.0e4) / ANNUAL_METHANOL

    with subtests.test("Levelized cost components"):
        for name, value in expected.items():
            assert prob.get_val(name, units="USD/kg") == pytest.approx(value), name

    with subtests.test("LCOM_meoh"):
        assert prob.get_val("LCOM_meoh", units="USD/kg") == pytest.approx(lcom_meoh)

    with subtests.test("LCOM is the sum of the plant and feedstock components"):
        feedstocks = ["LCOM_ng", "LCOM_co2", "LCOM_elec", "LCOM_h2"]
        assert prob.get_val("LCOM", units="USD/kg") == pytest.approx(
            lcom_meoh + sum(expected[name] for name in feedstocks)
        )


@pytest.mark.unit
def test_smr_methanol_cost(subtests, plant_config):
    tech_config = {
        "model_inputs": {
            "shared_parameters": SHARED_PARAMETERS,
            "cost_parameters": SMR_COST_PARAMETERS,
        }
    }
    prob = run_components(
        {"cost": SMRMethanolPlantCostModel},
        plant_config,
        tech_config,
        methanol_out=hourly(METHANOL_RATE),
        meoh_syn_cat_consume=3.0,
        meoh_atr_cat_consume=10.0,
        ng_consume=hourly(690.0),
        electricity_out=hourly(304.0),
    )
    ng_lhv_mmbtu_per_kg = convert_units(47.1, "MJ", "MBtu")
    expected = {
        "Fixed_OpEx": PLANT_CAPACITY_KGPY * 0.020675078,
        "Variable_OpEx": ANNUAL_METHANOL * 0.012271827,
        "meoh_syn_cat_cost": 3.0 * 615.274273,
        "meoh_atr_cat_cost": 10.0 * 747.9768786,
        "ng_cost": 690.0 * N_TIMESTEPS * ng_lhv_mmbtu_per_kg * 4.0,
    }
    elec_revenue = 304.0 * N_TIMESTEPS * PPA_PRICE

    with subtests.test("CapEx is the total overnight cost"):
        assert prob.get_val("CapEx", units="USD") == pytest.approx(
            PLANT_CAPACITY_KGPY * 0.782749307
        )

    with subtests.test("Annual cost components"):
        for name, value in expected.items():
            assert prob.get_val(name, units="USD/year") == pytest.approx(value), name

    with subtests.test("Electricity revenue uses the plant PPA price"):
        assert prob.get_val("elec_revenue", units="USD/year") == pytest.approx(elec_revenue)

    with subtests.test("OpEx is net of electricity revenue"):
        assert prob.get_val("OpEx", units="USD/year") == pytest.approx(
            sum(expected.values()) - elec_revenue
        )


@pytest.mark.unit
def test_smr_methanol_finance(subtests, plant_config):
    tech_config = {
        "model_inputs": {
            "shared_parameters": SHARED_PARAMETERS,
            "finance_parameters": FINANCE_PARAMETERS,
        }
    }
    prob = run_components(
        {"finance": SMRMethanolPlantFinanceModel},
        plant_config,
        tech_config,
        CapEx=1.0e7,
        Fixed_OpEx=2.0e5,
        Variable_OpEx=5.0e4,
        meoh_syn_cat_cost=6.0e3,
        meoh_atr_cat_cost=7.0e3,
        ng_cost=3.0e4,
        elec_revenue=1.0e4,
        methanol_out=hourly(METHANOL_RATE),
    )
    expected = {
        "LCOM_meoh_capex": 1.0e7 * 0.0707 * 1.093 / ANNUAL_METHANOL,
        "LCOM_meoh_fopex": 2.0e5 / ANNUAL_METHANOL,
        "LCOM_meoh_syn_cat": 6.0e3 / ANNUAL_METHANOL,
        "LCOM_meoh_atr_cat": 7.0e3 / ANNUAL_METHANOL,
        "LCOM_ng": 3.0e4 / ANNUAL_METHANOL,
        "LCOM_elec": -1.0e4 / ANNUAL_METHANOL,
    }
    lcom_meoh = (1.0e7 * 0.0707 * 1.093 + 2.0e5 + 5.0e4) / ANNUAL_METHANOL

    with subtests.test("Levelized cost components"):
        for name, value in expected.items():
            assert prob.get_val(name, units="USD/kg") == pytest.approx(value), name

    with subtests.test("LCOM_meoh"):
        assert prob.get_val("LCOM_meoh", units="USD/kg") == pytest.approx(lcom_meoh)

    with subtests.test("Electricity revenue reduces LCOM"):
        assert prob.get_val("LCOM", units="USD/kg") == pytest.approx(
            lcom_meoh + expected["LCOM_ng"] + expected["LCOM_elec"]
        )


@pytest.mark.unit
def test_smr_methanol_performance_cost_and_finance_together(subtests, plant_config):
    tech_config = {
        "model_inputs": {
            "shared_parameters": SHARED_PARAMETERS,
            "performance_parameters": SMR_PERFORMANCE_PARAMETERS,
            "cost_parameters": SMR_COST_PARAMETERS,
            "finance_parameters": FINANCE_PARAMETERS,
        }
    }
    prob = run_components(
        {
            "perf": SMRMethanolPlantPerformanceModel,
            "cost": SMRMethanolPlantCostModel,
            "finance": SMRMethanolPlantFinanceModel,
        },
        plant_config,
        tech_config,
    )
    annual_methanol = prob.get_val("total_methanol_produced", units="kg")[0]

    with subtests.test("Methanol output is limited by plant capacity"):
        assert 0 < annual_methanol <= PLANT_CAPACITY_KGPY

    with subtests.test("Electricity revenue follows the co-produced electricity"):
        assert prob.get_val("elec_revenue", units="USD/year") == pytest.approx(
            annual_methanol * 0.338415339 * PPA_PRICE
        )

    with subtests.test("LCOM components sum to LCOM"):
        components = ["LCOM_meoh", "LCOM_ng", "LCOM_elec"]
        assert prob.get_val("LCOM", units="USD/kg") == pytest.approx(
            sum(prob.get_val(name, units="USD/kg") for name in components)
        )
        assert prob.get_val("LCOM", units="USD/kg") > 0
