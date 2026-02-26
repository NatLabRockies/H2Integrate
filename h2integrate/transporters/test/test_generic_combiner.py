import numpy as np
import pytest
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
def tech_config_4_in(commodity, operation_mode):
    elec_combiner_dict = {
        "model_inputs": {
            "performance_parameters": {
                "commodity": commodity,
                "commodity_rate_units": "kg" if commodity == "hydrogen" else "kW",
                "in_streams": 4,
            }
        }
    }
    return elec_combiner_dict


@fixture
def tech_config(commodity, operation_mode):
    tech_config = {
        "model_inputs": {
            "performance_parameters": {
                "commodity": commodity,
                "commodity_rate_units": "kg" if commodity == "hydrogen" else "kW",
            }
        }
    }
    match operation_mode:
        case "consumption" | "production":
            operation = {"operation_mode": operation_mode}
            tech_config["model_inputs"]["performance_parameters"].update(operation)
        case _:
            pass
    return tech_config


@pytest.mark.unit
@pytest.mark.parametrize(
    "commodity,operation_mode",
    [("electricity", None), ("hydrogen", None)],
    ids=["electricity", "hydrogen"],
)
def test_generic_combiner_performance(subtests, plant_config, tech_config, commodity):
    is_electricity = commodity == "electricity"
    units = "kW" if is_electricity else "kg"
    prob = om.Problem()
    comp = GenericCombinerPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output(f"{commodity}_in1", val=np.zeros(8760), units=units)
    ivc.add_output(f"{commodity}_in2", val=np.zeros(8760), units=units)
    if is_electricity:
        ivc.add_output("rated_electricity_production1", val=0, units="kW")
        ivc.add_output("rated_electricity_production2", val=0, units="kW")
        ivc.add_output("electricity_capacity_factor1", val=np.zeros(30), units="unitless")
        ivc.add_output("electricity_capacity_factor2", val=np.zeros(30), units="unitless")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    commodity_input1 = rng.random(8760)
    commodity_input2 = rng.random(8760)
    commodity_output = commodity_input1 + commodity_input2
    prob.set_val(f"{commodity}_in1", commodity_input1, units=units)
    prob.set_val(f"{commodity}_in2", commodity_input2, units=units)
    if is_electricity:
        max1 = np.max(commodity_input1)
        max2 = np.max(commodity_input2)
        rated_electricity_output = max1 + max2
        cf_input1 = np.sum(commodity_input1) / (max1 * commodity_input1.size)
        cf_input2 = np.sum(commodity_input2) / (max2 * commodity_input2.size)
        prob.set_val("rated_electricity_production1", max1, units=units)
        prob.set_val("rated_electricity_production2", max2, units=units)
        prob.set_val("electricity_capacity_factor1", cf_input1 * np.ones(30), units="unitless")
        prob.set_val("electricity_capacity_factor2", cf_input2 * np.ones(30), units="unitless")

    prob.run_model()

    with subtests.test(f"combined {commodity}_out"):
        assert prob.get_val(f"{commodity}_out", units=units) == approx(commodity_output, rel=1e-5)

    if is_electricity:
        with subtests.test("combined rated_electricity_production"):
            assert prob.get_val("rated_electricity_production", units="kW") == approx(
                rated_electricity_output, rel=1e-5
            )
        with subtests.test("combined electricity_capacity_factor"):
            combined_cf = np.sum(commodity_output) / (
                rated_electricity_output * len(commodity_output)
            )
            assert prob.get_val("capacity_factor", units="unitless") == approx(
                combined_cf, rel=1e-5
            )


@pytest.mark.unit
@pytest.mark.parametrize(
    "commodity,operation_mode",
    [("electricity", None), ("hydrogen", None)],
)
def test_generic_combiner_performance_4_in(plant_config, tech_config_4_in, commodity):
    units = "kg" if commodity == "hydrogen" else "kW"
    prob = om.Problem()
    comp = GenericCombinerPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_4_in,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output(f"{commodity}_in1", val=np.zeros(8760), units=units)
    ivc.add_output(f"{commodity}_in2", val=np.zeros(8760), units=units)
    ivc.add_output(f"{commodity}_in3", val=np.zeros(8760), units=units)
    ivc.add_output(f"{commodity}_in4", val=np.zeros(8760), units=units)
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    commodity_input1 = rng.random(8760)
    commodity_input2 = rng.random(8760)
    commodity_input3 = rng.random(8760)
    commodity_input4 = rng.random(8760)
    commodity_output = commodity_input1 + commodity_input2 + commodity_input3 + commodity_input4

    prob.set_val(f"{commodity}_in1", commodity_input1, units=units)
    prob.set_val(f"{commodity}_in2", commodity_input2, units=units)
    prob.set_val(f"{commodity}_in3", commodity_input3, units=units)
    prob.set_val(f"{commodity}_in4", commodity_input4, units=units)
    prob.run_model()

    assert prob.get_val(f"{commodity}_out", units=units) == approx(commodity_output, rel=1e-5)


@pytest.mark.unit
@pytest.mark.parametrize(
    "commodity,operation_mode",
    [
        ("electricity", "production"),
        ("electricity", "consumption"),
        ("electricity", None),
        ("hydrogen", "production"),
        ("hydrogen", "consumption"),
        ("hydrogen", None),
    ],
)
def test_generic_summer_performance(plant_config, tech_config, commodity, operation_mode):
    """Tests generic setups for electricy and hydrogen production and consumption."""
    units = "kg" if commodity == "hydrogen" else "kW"
    mode = "consumed" if operation_mode == "consumption" else "produced"  # default is production
    prob = om.Problem()
    comp = GenericSummerPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output(f"{commodity}_in", val=np.zeros(8760), units=units)
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    commodity_input = rng.random(8760)
    total_commodity = sum(commodity_input)

    prob.set_val(f"{commodity}_in", commodity_input, units=units)
    prob.run_model()

    assert prob.get_val(f"total_{commodity}_{mode}", units=f"{units}*h/yr") == approx(
        total_commodity, rel=1e-5
    )
