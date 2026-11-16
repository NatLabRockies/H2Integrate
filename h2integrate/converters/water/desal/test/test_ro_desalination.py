import numpy as np
import pytest
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.converters.water.desal.desalination import (
    SALINITY_PROPERTIES,
    ReverseOsmosisCostModel,
    ReverseOsmosisPerformanceModel,
    ReverseOsmosisPerformanceModelConfig,
)


N_TIMESTEPS = 8760


@fixture
def plant_config():
    plant = {
        "plant_life": 30,
        "simulation": {
            "dt": 3600,
            "n_timesteps": N_TIMESTEPS,
        },
    }

    return {"plant": plant}


def make_problem(plant_config, salinity="brackish", electricity=1e4, feedwater=1e4, **params):
    """Set up a performance model with ample (or user-specified) electricity and feedwater."""
    performance_parameters = {
        "freshwater_capacity_kg_per_hr": 10000,
        "salinity": salinity,
        "freshwater_density": 997,
        **params,
    }
    tech_config = {"model_inputs": {"performance_parameters": performance_parameters}}

    prob = om.Problem()
    comp = ReverseOsmosisPerformanceModel(plant_config=plant_config, tech_config=tech_config)
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("electricity_in", electricity, units="kW")
    prob.set_val("feedwater_in", feedwater, units="m**3/h")
    prob.run_model()
    return prob


@pytest.mark.unit
def test_brackish_desal_outputs(plant_config, subtests):
    prob = make_problem(plant_config)

    commodity = "water"
    commodity_amount_units = "m**3"
    commodity_rate_units = "m**3/h"
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    with subtests.test("0 <= replacement_schedule <=1"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("comp.replacement_schedule", units="unitless")) == plant_life

    with subtests.test("0 <= capacity_factor (unitless) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") <= 1)

    with subtests.test("1 <= capacity_factor (percent) <=100"):
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") >= 1)
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") <= 100)

    with subtests.test("capacity_factor length"):
        assert len(prob.get_val("comp.capacity_factor", units="unitless")) == plant_life

    with subtests.test(f"rated_{commodity}_production > 0"):
        assert np.all(
            prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units) > 0
        )

    with subtests.test(f"total_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units) > 0
        )

    with subtests.test(f"annual_{commodity}_produced"):
        annual_production = prob.get_val(
            f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
        )
        assert len(annual_production) == plant_life
        assert np.all(annual_production > 0)
        assert np.all(annual_production[1:] == annual_production[0])

    with subtests.test(f"{commodity}_out length"):
        assert len(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units)) == n_timesteps

    with subtests.test("input and output lengths"):
        for name in ("electricity_in", "feedwater_in"):
            assert len(prob.get_val(f"comp.{name}")) == n_timesteps
        for name in ("electricity_consumed", "feedwater_consumed"):
            assert len(prob.get_val(f"comp.{name}")) == n_timesteps

    with subtests.test("operational_life default value"):
        assert prob.get_val("comp.operational_life", units="yr") == plant_life
    with subtests.test("replacement_schedule value"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


@pytest.mark.regression
@pytest.mark.parametrize(
    "salinity,feedwater,electricity",
    [("brackish", 13.37, 15.04), ("seawater", 20.06, 40.12)],
)
def test_performance_at_capacity(plant_config, salinity, feedwater, electricity, subtests):
    prob = make_problem(plant_config, salinity=salinity)

    with subtests.test("fresh water"):
        assert prob.get_val("water_out", units="m**3/h") == approx(10.03, rel=1e-3)
    with subtests.test("mass"):
        assert prob.get_val("mass", units="kg") == approx(3477.43, rel=1e-3)
    with subtests.test("footprint"):
        assert prob.get_val("footprint", units="m**2") == approx(4.68, rel=1e-3)
    with subtests.test("feedwater consumed"):
        assert prob.get_val("feedwater_consumed", units="m**3/h") == approx(feedwater, rel=1e-3)
    with subtests.test("electricity consumed"):
        assert prob.get_val("electricity_consumed", units="kW") == approx(electricity, rel=1e-3)
    with subtests.test("capacity factor"):
        assert prob.get_val("capacity_factor", units="unitless") == approx(1.0)


@pytest.mark.regression
def test_limiting_resource(plant_config, subtests):
    capacity = 10000 / 997  # m**3/h

    # Seawater: 0.5 recovery and 4 kWh/m^3. Alternate which resource is limiting.
    electricity = np.full(N_TIMESTEPS, 1e4)
    feedwater = np.full(N_TIMESTEPS, 1e4)
    electricity[0] = 20.0  # limits to 5 m^3/h
    feedwater[1] = 6.0  # limits to 3 m^3/h
    electricity[2] = 0.0  # no electricity, no water
    electricity[3] = 20.0  # electricity limits to 5 m^3/h, feedwater would allow 10 m^3/h
    feedwater[3] = 20.0

    prob = make_problem(
        plant_config, salinity="seawater", electricity=electricity, feedwater=feedwater
    )
    water_out = prob.get_val("water_out", units="m**3/h")

    with subtests.test("electricity limited"):
        assert water_out[0] == approx(5.0)
    with subtests.test("feedwater limited"):
        assert water_out[1] == approx(3.0)
    with subtests.test("no electricity"):
        assert water_out[2] == 0.0
    with subtests.test("both limiting"):
        assert water_out[3] == approx(5.0)
    with subtests.test("capacity limited"):
        assert water_out[4] == approx(capacity)

    with subtests.test("consumption matches production"):
        assert prob.get_val("electricity_consumed", units="kW") == approx(water_out * 4.0)
        assert prob.get_val("feedwater_consumed", units="m**3/h") == approx(water_out / 0.5)

    with subtests.test("total production"):
        assert prob.get_val("total_water_produced", units="m**3") == approx(water_out.sum())
    with subtests.test("capacity factor"):
        assert prob.get_val("capacity_factor", units="unitless") == approx(
            water_out.sum() / (capacity * N_TIMESTEPS)
        )


@pytest.mark.regression
def test_config_values_are_inputs(plant_config, subtests):
    prob = make_problem(plant_config, salinity="seawater")
    base_water = prob.get_val("water_out", units="m**3/h")[0]

    with subtests.test("config values are inputs"):
        for name in ("freshwater_capacity", "freshwater_density"):
            assert name in prob.model.comp._var_rel_names["input"]

    with subtests.test("capacity can be changed"):
        prob.set_val("freshwater_capacity", 5000, units="kg/h")
        prob.run_model()
        assert prob.get_val("water_out", units="m**3/h")[0] == approx(base_water / 2)
        assert prob.get_val("mass", units="kg") == approx(3477.43 / 2, rel=1e-3)

    with subtests.test("density can be changed"):
        prob.set_val("freshwater_capacity", 10000, units="kg/h")
        prob.set_val("freshwater_density", 1994, units="kg/m**3")
        prob.run_model()
        assert prob.get_val("water_out", units="m**3/h")[0] == approx(base_water / 2)


@pytest.mark.regression
@pytest.mark.parametrize("salinity", ["seawater", "brackish"])
def test_timestep_independence(salinity, subtests):
    """Uniform inputs over half a year give the same answers at 5 minute and 1 hour steps."""
    results = {}
    for dt, n_timesteps in [(300, 52560), (3600, 4380)]:
        config = {"plant": {"plant_life": 30, "simulation": {"dt": dt, "n_timesteps": n_timesteps}}}
        # Electricity limits production at 5 m^3/h, below the 10.03 m^3/h capacity
        electricity = 5.0 * (4.0 if salinity == "seawater" else 1.5)
        prob = make_problem(config, salinity=salinity, electricity=electricity, feedwater=1e4)
        results[dt] = {
            name: prob.get_val(name, units=units)
            for name, units in [
                ("water_out", "m**3/h"),
                ("electricity_consumed", "kW"),
                ("feedwater_consumed", "m**3/h"),
                ("total_water_produced", "m**3"),
                ("annual_water_produced", "m**3/year"),
                ("capacity_factor", "unitless"),
                ("rated_water_production", "m**3/h"),
            ]
        }

    fast, slow = results[300], results[3600]

    for name in ("electricity_consumed", "feedwater_consumed", "rated_water_production"):
        with subtests.test(f"{name} rate"):
            assert fast[name][0] == approx(slow[name][0])

    with subtests.test("water_out rate"):
        assert fast["water_out"][0] == approx(5.0)
        assert slow["water_out"][0] == approx(5.0)

    with subtests.test("total_water_produced"):
        assert fast["total_water_produced"] == approx(slow["total_water_produced"])
        assert slow["total_water_produced"] == approx(5.0 * 4380)

    with subtests.test("annual_water_produced"):
        assert fast["annual_water_produced"] == approx(slow["annual_water_produced"])
        assert slow["annual_water_produced"][0] == approx(5.0 * 8760)

    with subtests.test("capacity_factor"):
        assert fast["capacity_factor"] == approx(slow["capacity_factor"])


@pytest.mark.regression
def test_one_second_timestep(subtests):
    config = {"plant": {"plant_life": 30, "simulation": {"dt": 1, "n_timesteps": 3600}}}
    prob = make_problem(config, salinity="brackish", electricity=7.5, feedwater=1e4)

    with subtests.test("water_out rate"):
        assert prob.get_val("water_out", units="m**3/h")[0] == approx(5.0)
    with subtests.test("one hour of production"):
        assert prob.get_val("total_water_produced", units="m**3") == approx(5.0)
    with subtests.test("annual production"):
        assert prob.get_val("annual_water_produced", units="m**3/year")[0] == approx(5.0 * 8760)


@pytest.mark.unit
def test_config_salinity_values(subtests):
    with subtests.test("seawater values"):
        assert SALINITY_PROPERTIES["seawater"]["recovery_ratio"] == 0.5
        assert SALINITY_PROPERTIES["seawater"]["specific_energy_consumption"] == 4.0

    with subtests.test("brackish values"):
        assert SALINITY_PROPERTIES["brackish"]["recovery_ratio"] == 0.75
        assert SALINITY_PROPERTIES["brackish"]["specific_energy_consumption"] == 1.5

    with subtests.test("invalid salinity"):
        with pytest.raises(ValueError):
            ReverseOsmosisPerformanceModelConfig(freshwater_capacity_kg_per_hr=1, salinity="fresh")


@pytest.mark.regression
def test_ro_desalination_cost(subtests):
    tech_config = {
        "model_inputs": {
            "cost_parameters": {
                "freshwater_capacity_kg_per_hr": 10000,
            },
        }
    }

    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }

    prob = om.Problem()
    comp = ReverseOsmosisCostModel(tech_config=tech_config, plant_config=plant_config)
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    prob.setup()
    prob.run_model()

    with subtests.test("capex"):
        assert prob.get_val("CapEx", units="USD") == approx(91372, rel=1e-2)
    with subtests.test("opex"):
        assert prob.get_val("OpEx", units="USD/year") == approx(13447, rel=1e-2)

    with subtests.test("capacity is an input"):
        prob.set_val("rated_freshwater_production_capacity", 20000 / 3600, units="kg/s")
        prob.run_model()
        assert prob.get_val("CapEx", units="USD") == approx(2 * 91372, rel=1e-2)
