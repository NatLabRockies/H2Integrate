import numpy as np
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.transporters.generic_summer import GenericSummerPerformanceModel
from h2integrate.transporters.generic_combiner import GenericCombinerPerformanceModel


rng = np.random.default_rng(seed=0)


@fixture
def plant_config():
    plant_dict = {
        "plant": {
            "plant_life": 30,
            "simulation": {"n_timesteps": 8760, "dt": 3600},
        }
    }
    return plant_dict


@fixture
def combiner_tech_config_electricity():
    elec_combiner_dict = {
        "model_inputs": {
            "performance_parameters": {"commodity": "electricity", "commodity_rate_units": "kW"}
        }
    }
    return elec_combiner_dict


@fixture
def combiner_tech_config_electricity_4_in():
    elec_combiner_dict = {
        "model_inputs": {
            "performance_parameters": {
                "commodity": "electricity",
                "commodity_rate_units": "kW",
                "in_streams": 4,
            }
        }
    }
    return elec_combiner_dict


@fixture
def combiner_tech_config_hydrogen():
    h2_combiner_dict = {
        "model_inputs": {
            "performance_parameters": {"commodity": "hydrogen", "commodity_rate_units": "kg"}
        }
    }
    return h2_combiner_dict


@fixture
def summer_tech_config_electricity_consumption():
    elec_summer_dict = {
        "model_inputs": {
            "performance_parameters": {
                "commodity": "electricity",
                "commodity_rate_units": "kW",
                "operation_mode": "consumption",
            }
        }
    }
    return elec_summer_dict


@fixture
def summer_tech_config_hydrogen_consumption():
    h2_summer_dict = {
        "model_inputs": {
            "performance_parameters": {
                "commodity": "hydrogen",
                "commodity_rate_units": "kg",
                "operation_mode": "consumption",
            }
        }
    }
    return h2_summer_dict


@fixture
def summer_tech_config_electricity_production():
    elec_summer_dict = {
        "model_inputs": {
            "performance_parameters": {
                "commodity": "electricity",
                "commodity_rate_units": "kW",
                "operation_mode": "production",
            }
        }
    }
    return elec_summer_dict


@fixture
def summer_tech_config_hydrogen_production():
    h2_summer_dict = {
        "model_inputs": {
            "performance_parameters": {
                "commodity": "hydrogen",
                "commodity_rate_units": "kg",
                "operation_mode": "production",
            }
        }
    }
    return h2_summer_dict


def test_generic_combiner_performance_power(
    plant_config, combiner_tech_config_electricity, subtests
):
    prob = om.Problem()
    comp = GenericCombinerPerformanceModel(
        plant_config=plant_config, tech_config=combiner_tech_config_electricity, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output("electricity_in1", val=np.zeros(8760), units="kW")
    ivc.add_output("electricity_in2", val=np.zeros(8760), units="kW")
    ivc.add_output("rated_electricity_production1", val=0, units="kW")
    ivc.add_output("rated_electricity_production2", val=0, units="kW")
    ivc.add_output("electricity_capacity_factor1", val=np.zeros(30), units="unitless")
    ivc.add_output("electricity_capacity_factor2", val=np.zeros(30), units="unitless")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    electricity_input1 = rng.random(8760)
    electricity_input2 = rng.random(8760)
    electricity_output = electricity_input1 + electricity_input2
    rated_electricity_output = np.max(electricity_input1) + np.max(electricity_input2)
    cf_input1 = np.sum(electricity_input1) / (np.max(electricity_input1) * len(electricity_input1))
    cf_input2 = np.sum(electricity_input2) / (np.max(electricity_input2) * len(electricity_input2))
    prob.set_val("electricity_in1", electricity_input1, units="kW")
    prob.set_val("electricity_in2", electricity_input2, units="kW")
    prob.set_val("rated_electricity_production1", np.max(electricity_input1), units="kW")
    prob.set_val("rated_electricity_production2", np.max(electricity_input2), units="kW")
    prob.set_val("electricity_capacity_factor1", cf_input1 * np.ones(30), units="unitless")
    prob.set_val("electricity_capacity_factor2", cf_input2 * np.ones(30), units="unitless")
    prob.run_model()

    with subtests.test("combined electricity_out"):
        assert prob.get_val("electricity_out", units="kW") == approx(electricity_output, rel=1e-5)
    with subtests.test("combined rated_electricity_production"):
        assert prob.get_val("rated_electricity_production", units="kW") == approx(
            rated_electricity_output, rel=1e-5
        )
    with subtests.test("combined electricity_capacity_factor"):
        combined_cf = np.sum(electricity_output) / (
            rated_electricity_output * len(electricity_output)
        )
        assert prob.get_val("electricity_capacity_factor", units="unitless") == approx(
            combined_cf, rel=1e-5
        )


def test_generic_combiner_performance_power_4_in(
    plant_config, combiner_tech_config_electricity_4_in
):
    prob = om.Problem()
    comp = GenericCombinerPerformanceModel(
        plant_config=plant_config,
        tech_config=combiner_tech_config_electricity_4_in,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output("electricity_in1", val=np.zeros(8760), units="kW")
    ivc.add_output("electricity_in2", val=np.zeros(8760), units="kW")
    ivc.add_output("electricity_in3", val=np.zeros(8760), units="kW")
    ivc.add_output("electricity_in4", val=np.zeros(8760), units="kW")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    electricity_input1 = rng.random(8760)
    electricity_input2 = rng.random(8760)
    electricity_input3 = rng.random(8760)
    electricity_input4 = rng.random(8760)
    electricity_output = (
        electricity_input1 + electricity_input2 + electricity_input3 + electricity_input4
    )

    prob.set_val("electricity_in1", electricity_input1, units="kW")
    prob.set_val("electricity_in2", electricity_input2, units="kW")
    prob.set_val("electricity_in3", electricity_input3, units="kW")
    prob.set_val("electricity_in4", electricity_input4, units="kW")
    prob.run_model()

    assert prob.get_val("electricity_out", units="kW") == approx(electricity_output, rel=1e-5)


def test_generic_combiner_performance_hydrogen(plant_config, combiner_tech_config_hydrogen):
    prob = om.Problem()
    comp = GenericCombinerPerformanceModel(
        plant_config=plant_config, tech_config=combiner_tech_config_hydrogen, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output("hydrogen_in1", val=np.zeros(8760), units="kg")
    ivc.add_output("hydrogen_in2", val=np.zeros(8760), units="kg")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    hydrogen_input1 = rng.random(8760)
    hydrogen_input2 = rng.random(8760)
    hydrogen_output = hydrogen_input1 + hydrogen_input2

    prob.set_val("hydrogen_in1", hydrogen_input1, units="kg")
    prob.set_val("hydrogen_in2", hydrogen_input2, units="kg")
    prob.run_model()

    assert prob.get_val("hydrogen_out", units="kg") == approx(hydrogen_output, rel=1e-5)


def test_generic_consumption_summer_performance_electricity(
    plant_config, summer_tech_config_electricity_consumption
):
    prob = om.Problem()
    comp = GenericSummerPerformanceModel(
        plant_config=plant_config,
        tech_config=summer_tech_config_electricity_consumption,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output("electricity_in", val=np.zeros(8760), units="kW")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    electricity_input = rng.random(8760)
    total_electricity_consumed = sum(electricity_input)

    prob.set_val("electricity_in", electricity_input, units="kW")
    prob.run_model()

    assert prob.get_val("total_electricity_consumed") == approx(
        total_electricity_consumed, rel=1e-5
    )


def test_generic_consumption_summer_performance_hydrogen(
    plant_config, summer_tech_config_hydrogen_consumption
):
    prob = om.Problem()
    comp = GenericSummerPerformanceModel(
        plant_config=plant_config,
        tech_config=summer_tech_config_hydrogen_consumption,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output("hydrogen_in", val=np.zeros(8760), units="kg")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    hydrogen_input = rng.random(8760)
    total_hydrogen_consumed = sum(hydrogen_input)

    prob.set_val("hydrogen_in", hydrogen_input, units="kg")
    prob.run_model()

    assert prob.get_val("total_hydrogen_consumed") == approx(total_hydrogen_consumed, rel=1e-5)


def test_generic_production_summer_performance_electricity(
    plant_config, summer_tech_config_electricity_production
):
    prob = om.Problem()
    comp = GenericSummerPerformanceModel(
        plant_config=plant_config,
        tech_config=summer_tech_config_electricity_production,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output("electricity_in", val=np.zeros(8760), units="kW")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    electricity_input = rng.random(8760)
    total_electricity_produced = sum(electricity_input)

    prob.set_val("electricity_in", electricity_input, units="kW")
    prob.run_model()

    assert prob.get_val("total_electricity_produced") == approx(
        total_electricity_produced, rel=1e-5
    )


def test_generic_production_summer_performance_hydrogen(
    plant_config, summer_tech_config_hydrogen_production
):
    prob = om.Problem()
    comp = GenericSummerPerformanceModel(
        plant_config=plant_config,
        tech_config=summer_tech_config_hydrogen_production,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output("hydrogen_in", val=np.zeros(8760), units="kg")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    hydrogen_input = rng.random(8760)
    total_hydrogen_produced = sum(hydrogen_input)

    prob.set_val("hydrogen_in", hydrogen_input, units="kg")
    prob.run_model()

    assert prob.get_val("total_hydrogen_produced") == approx(total_hydrogen_produced, rel=1e-5)


def test_generic_summer_default_mode_is_production(plant_config):
    """Test that the default operation mode is production when not specified."""
    tech_config = {
        "model_inputs": {
            "performance_parameters": {
                "commodity": "electricity",
                "commodity_rate_units": "kW",
                # Note: operation_mode not specified, should default to production
            }
        }
    }

    prob = om.Problem()
    comp = GenericSummerPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output("electricity_in", val=np.zeros(8760), units="kW")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    electricity_input = rng.random(8760)
    total_electricity_produced = sum(electricity_input)

    prob.set_val("electricity_in", electricity_input, units="kW")
    prob.run_model()

    # Should have production output, not consumption
    assert prob.get_val("total_electricity_produced") == approx(
        total_electricity_produced, rel=1e-5
    )
