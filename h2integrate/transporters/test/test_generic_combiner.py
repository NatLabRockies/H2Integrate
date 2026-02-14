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
                "commodity_units": "kg" if commodity == "hydrogen" else "kW",
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
                "commodity_units": "kg" if commodity == "hydrogen" else "kW",
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
def test_generic_combiner_performance(plant_config, tech_config, commodity):
    units = "kg" if commodity == "hydrogen" else "kW"
    prob = om.Problem()
    comp = GenericCombinerPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    ivc = om.IndepVarComp()
    ivc.add_output(f"{commodity}_in1", val=np.zeros(8760), units=units)
    ivc.add_output(f"{commodity}_in2", val=np.zeros(8760), units=units)
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()

    commodity_input1 = rng.random(8760)
    commodity_input2 = rng.random(8760)
    commodity_output = commodity_input1 + commodity_input2

    prob.set_val(f"{commodity}_in1", commodity_input1, units=units)
    prob.set_val(f"{commodity}_in2", commodity_input2, units=units)
    prob.run_model()

    assert prob.get_val(f"{commodity}_out", units=units) == approx(commodity_output, rel=1e-5)


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

    assert prob.get_val(f"total_{commodity}_{mode}") == approx(total_commodity, rel=1e-5)
