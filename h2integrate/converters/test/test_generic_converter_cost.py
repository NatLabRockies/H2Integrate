import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.converters.generic_converter_cost import (
    GenericConverterCostModel,
    GenericConverterCostConfig,
)


@fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": 8760,
            },
        },
    }
    return plant_config


@fixture
def model_inputs():
    tech_config = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "commodity_amount_units": "kg",
        "unit_capex": 10.0,
        "unit_opex": None,
        "opex_fraction": 0.1,
        "unit_varopex": 0.0,
        "cost_year": 2022,
    }
    return {"cost_parameters": tech_config}


@pytest.mark.unit
def test_generic_converter_cost_config(model_inputs, subtests):
    expected_msg = "Please provide either a value for unit_opex or a value for opex_fraction"

    model_inputs["cost_parameters"]["unit_opex"] = 10.0
    model_inputs["cost_parameters"]["opex_fraction"] = 0.1
    with subtests.test("Config error: two opex inputs provided"):
        with pytest.raises(KeyError) as excinfo:
            config = GenericConverterCostConfig.from_dict(
                merge_shared_inputs(model_inputs, "cost"),
                strict=True,
                additional_cls_name="test",
            )
            assert str(excinfo.value) == expected_msg

    model_inputs["cost_parameters"]["unit_opex"] = None
    model_inputs["cost_parameters"]["opex_fraction"] = None
    with subtests.test("Config error: No opex input provided"):
        with pytest.raises(KeyError) as excinfo:
            GenericConverterCostConfig.from_dict(
                merge_shared_inputs(model_inputs, "cost"),
                strict=True,
                additional_cls_name="test",
            )
            assert str(excinfo.value) == expected_msg

    model_inputs["cost_parameters"]["unit_opex"] = None
    model_inputs["cost_parameters"]["opex_fraction"] = 0.1
    with subtests.test("Config instantiation: opex fraction provided"):
        config = GenericConverterCostConfig.from_dict(
            merge_shared_inputs(model_inputs, "cost"),
            strict=True,
            additional_cls_name="test",
        )
        assert config.opex_fraction == 0.1

    model_inputs["cost_parameters"]["unit_opex"] = 10.0
    model_inputs["cost_parameters"]["opex_fraction"] = None
    with subtests.test("Config instantiation: unit opex provided"):
        config = GenericConverterCostConfig.from_dict(
            merge_shared_inputs(model_inputs, "cost"),
            strict=True,
            additional_cls_name="test",
        )
        assert config.unit_opex == 10.0


@pytest.mark.unit
def test_generic_converter_cost_opex_fraction(plant_config, model_inputs, subtests):
    model_inputs["cost_parameters"]["unit_opex"] = None
    model_inputs["cost_parameters"]["opex_fraction"] = 0.1

    prob = om.Problem()

    comp = GenericConverterCostModel(
        plant_config=plant_config,
        tech_config={"model_inputs": model_inputs},
    )

    opex_fraction = 0.1
    unit_capex = 10.0
    unit_varom = 5.0
    hourly_rated_production = 1.0
    annual_production = 8760 * hourly_rated_production
    rated_prod_comp = om.IndepVarComp(
        name="rated_hydrogen_production", val=hourly_rated_production, units="kg/h"
    )
    annual_prod_comp = om.IndepVarComp(
        name="annual_hydrogen_produced", val=annual_production, shape=30, units="kg/yr"
    )
    prob.model.add_subsystem("cost", comp, promotes=["*"])
    prob.model.add_subsystem("IVC1", rated_prod_comp, promotes=["*"])
    prob.model.add_subsystem("IVC2", annual_prod_comp, promotes=["*"])

    prob.setup()

    prob.set_val("cost.fixed_opex_ratio", val=opex_fraction, units="unitless")
    prob.set_val("cost.unit_capex", val=unit_capex, units="USD/(kg/h)")
    prob.set_val("cost.unit_varopex", val=unit_varom, units="USD/kg")
    prob.run_model()

    with subtests.test("CapEx"):
        expected_capex = unit_capex * hourly_rated_production
        assert pytest.approx(expected_capex, rel=1e-6) == prob.get_val("CapEx", units="USD")

    with subtests.test("Fixed OpEx"):
        expected_opex = expected_capex * opex_fraction
        assert pytest.approx(expected_opex, rel=1e-6) == prob.get_val("OpEx", units="USD/year")

    with subtests.test("Variable OpEx"):
        expected_varopex = np.full(30, unit_varom * annual_production)
        assert pytest.approx(expected_varopex, rel=1e-6) == prob.get_val(
            "VarOpEx", units="USD/year"
        )


@pytest.mark.unit
def test_generic_converter_cost_opex_value(plant_config, model_inputs, subtests):
    model_inputs["cost_parameters"]["unit_opex"] = 1.0
    model_inputs["cost_parameters"]["opex_fraction"] = None

    prob = om.Problem()

    comp = GenericConverterCostModel(
        plant_config=plant_config,
        tech_config={"model_inputs": model_inputs},
    )

    unit_opex = 1.0
    unit_capex = 10.0
    unit_varom = 5.0
    hourly_rated_production = 1.0
    annual_production = 8760 * hourly_rated_production
    rated_prod_comp = om.IndepVarComp(
        name="rated_hydrogen_production", val=hourly_rated_production, units="kg/h"
    )
    annual_prod_comp = om.IndepVarComp(
        name="annual_hydrogen_produced", val=annual_production, shape=30, units="kg/yr"
    )
    prob.model.add_subsystem("cost", comp, promotes=["*"])
    prob.model.add_subsystem("IVC1", rated_prod_comp, promotes=["*"])
    prob.model.add_subsystem("IVC2", annual_prod_comp, promotes=["*"])

    prob.setup()

    prob.set_val("cost.unit_opex", val=unit_opex, units="USD/(kg/h)/year")
    prob.set_val("cost.unit_capex", val=unit_capex, units="USD/(kg/h)")
    prob.set_val("cost.unit_varopex", val=unit_varom, units="USD/kg")
    prob.run_model()

    with subtests.test("CapEx"):
        expected_capex = unit_capex * hourly_rated_production
        assert pytest.approx(expected_capex, rel=1e-6) == prob.get_val("CapEx", units="USD")

    with subtests.test("Fixed OpEx"):
        expected_opex = hourly_rated_production * unit_opex
        assert pytest.approx(expected_opex, rel=1e-6) == prob.get_val("OpEx", units="USD/year")

    with subtests.test("Variable OpEx"):
        expected_varopex = np.full(30, unit_varom * annual_production)
        assert pytest.approx(expected_varopex, rel=1e-6) == prob.get_val(
            "VarOpEx", units="USD/year"
        )
