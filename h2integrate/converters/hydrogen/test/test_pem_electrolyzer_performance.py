import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.hydrogen.pem_electrolyzer import ECOElectrolyzerPerformanceModel


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
    }
    return plant_config


@fixture
def tech_config():
    config = {
        "model_inputs": {
            "performance_parameters": {
                "n_clusters": 4.0,
                "location": "onshore",
                "cluster_rating_MW": 10,
                "eol_eff_percent_loss": 10.0,
                "uptime_hours_until_eol": 8000,
                "include_degradation_penalty": True,
                "turndown_ratio": 0.1,
                "electrolyzer_capex": 10.0,
            }
        }
    }
    return config


def _run_electrolyzer(plant_config, tech_config, power_profile, command_value=None):
    prob = om.Problem()
    comp = ECOElectrolyzerPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.set_val("comp.electricity_in", power_profile, units="MW")
    if command_value is not None:
        prob.set_val("comp.hydrogen_command_value", command_value, units="kg/h")
    prob.run_model()
    return prob


@pytest.mark.unit
def test_electrolyzer_outputs(tech_config, plant_config, subtests):
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob = om.Problem()
    comp = ECOElectrolyzerPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    power_profile = np.ones(n_timesteps) * 32.0
    prob.set_val("comp.electricity_in", power_profile, units="MW")

    prob.run_model()

    commodity = "hydrogen"
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
        assert np.any(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


@pytest.mark.regression
def test_electrolyzer_results(tech_config, plant_config, subtests):
    prob = om.Problem()
    comp = ECOElectrolyzerPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    power_profile = np.full(8760, 32.0)
    prob.set_val("comp.electricity_in", power_profile, units="MW")

    prob.run_model()

    with subtests.test("Total hydrogen produced"):
        assert (
            pytest.approx(5297814.89908964, rel=1e-6)
            == prob.get_val("comp.hydrogen_out", units="kg/h").sum()
        )

    with subtests.test("Total oxygen produced"):
        assert (
            pytest.approx(42045916.90741967, rel=1e-6)
            == prob.get_val("comp.oxygen_out", units="kg/h").sum()
        )

    with subtests.test("Year 0 capacity factor"):
        assert (
            pytest.approx(77.10460139, rel=1e-6)
            == prob.get_val("comp.capacity_factor", units="percent")[0]
        )

    with subtests.test("Rated H2 production"):
        assert pytest.approx(784.3544735823235, rel=1e-6) == prob.get_val(
            "comp.rated_hydrogen_production", units="kg/h"
        )

    with subtests.test("Rated O2 production"):
        assert pytest.approx(6225.00099576, rel=1e-6) == prob.get_val(
            "comp.rated_oxygen_production", units="kg/h"
        )

    with subtests.test("H2: CF*Rated = Annual"):
        np.testing.assert_allclose(
            prob.get_val("comp.rated_hydrogen_production", units="kg/h")
            * prob.get_val("comp.capacity_factor", units="unitless")
            * 8760,
            prob.get_val("comp.annual_hydrogen_produced", units="kg/yr"),
            rtol=1e-6,
        )
    with subtests.test("O2: CF*Rated = Annual"):
        np.testing.assert_allclose(
            prob.get_val("comp.rated_oxygen_production", units="kg/h")
            * prob.get_val("comp.capacity_factor", units="unitless")
            * 8760,
            prob.get_val("comp.annual_oxygen_produced", units="kg/yr"),
            rtol=1e-6,
        )

    # 10 kg water consumed per kg of H2 produced
    with subtests.test("Water consumption"):
        total_water_consumed_kg = prob.get_val("comp.water_consumed", units="galUS/h").sum() / 3.79
        total_h2_produced = prob.get_val("comp.hydrogen_out", units="kg/h").sum()
        assert pytest.approx(10.0, rel=1e-6) == total_water_consumed_kg / total_h2_produced

    with subtests.test("Electricity consumption"):
        total_electricity_consumed = prob.get_val("comp.electricity_consumed", units="kW").sum()

        assert (
            pytest.approx(52.72613937672745, rel=1e-6)
            == total_electricity_consumed / total_h2_produced
        )


@pytest.mark.unit
def test_electrolyzer_outputs_never_operated(tech_config, plant_config, subtests):
    int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    prob = om.Problem()
    comp = ECOElectrolyzerPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    power_profile = np.zeros(n_timesteps)
    prob.set_val("comp.electricity_in", power_profile, units="MW")

    prob.run_model()

    with subtests.test("Time until replacement is same as config"):
        assert (
            prob.get_val("comp.time_until_replacement")[0]
            == tech_config["model_inputs"]["performance_parameters"]["uptime_hours_until_eol"]
        )

    with subtests.test("Zero efficiency"):
        assert prob.get_val("comp.efficiency") == 0.0

    with subtests.test("Zero hydrogen production"):
        assert prob.get_val("comp.hydrogen_out").sum() == 0.0

    with subtests.test("Zero oxygen production"):
        assert prob.get_val("comp.oxygen_out").sum() == 0.0

    with subtests.test("Zero water consumption"):
        assert prob.get_val("comp.water_consumed").sum() == 0.0

    with subtests.test("Zero power consumption"):
        assert prob.get_val("comp.electricity_consumed").sum() == 0.0

    with subtests.test("Zero capacity factor"):
        assert prob.get_val("comp.capacity_factor").sum() == 0.0


@pytest.mark.unit
def test_electrolyzer_slc_clips_hydrogen_linked_outputs(tech_config, plant_config, subtests):
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
    power_profile = np.full(n_timesteps, 32.0)
    reference_prob = _run_electrolyzer(plant_config, tech_config, power_profile)
    reference_hydrogen = reference_prob.get_val("comp.hydrogen_out", units="kg/h")

    command_value = np.full(n_timesteps, 1e9)
    command_value[:24] = reference_hydrogen[:24] * 0.5
    slc_plant_config = plant_config | {"system_level_control": {}}
    slc_prob = _run_electrolyzer(
        slc_plant_config, tech_config, power_profile, command_value=command_value
    )

    hydrogen_out = slc_prob.get_val("comp.hydrogen_out", units="kg/h")
    clipped_hours = (np.arange(n_timesteps) < 24) & (reference_hydrogen > 0.0)
    annual_scale = hydrogen_out.sum() / reference_hydrogen.sum()

    with subtests.test("Commanded hydrogen is clipped"):
        assert np.any(clipped_hours)
        np.testing.assert_allclose(hydrogen_out[clipped_hours], command_value[clipped_hours])
        assert np.all(hydrogen_out <= command_value)

    with subtests.test("Electricity per hydrogen matches the unclipped operating point"):
        np.testing.assert_allclose(
            slc_prob.get_val("comp.electricity_consumed", units="kW")[clipped_hours]
            / hydrogen_out[clipped_hours],
            reference_prob.get_val("comp.electricity_consumed", units="kW")[clipped_hours]
            / reference_hydrogen[clipped_hours],
            rtol=1e-12,
        )
        assert np.all(
            slc_prob.get_val("comp.electricity_consumed", units="kW")
            <= slc_prob.get_val("comp.electricity_in", units="kW")
        )

    with subtests.test("Oxygen and water scale with commanded hydrogen"):
        np.testing.assert_allclose(
            slc_prob.get_val("comp.oxygen_out", units="kg/h")[clipped_hours]
            / hydrogen_out[clipped_hours],
            reference_prob.get_val("comp.oxygen_out", units="kg/h")[clipped_hours]
            / reference_hydrogen[clipped_hours],
            rtol=1e-12,
        )
        np.testing.assert_allclose(
            slc_prob.get_val("comp.water_consumed", units="galUS/h")[clipped_hours]
            / hydrogen_out[clipped_hours],
            reference_prob.get_val("comp.water_consumed", units="galUS/h")[clipped_hours]
            / reference_hydrogen[clipped_hours],
            rtol=1e-12,
        )

    with subtests.test("Totals and annual hydrogen-linked schedules follow clipping"):
        assert slc_prob.get_val("comp.total_hydrogen_produced", units="kg")[0] == pytest.approx(
            hydrogen_out.sum()
        )
        for output_name in (
            "annual_hydrogen_produced",
            "annual_oxygen_produced",
            "capacity_factor",
        ):
            np.testing.assert_allclose(
                slc_prob.get_val(f"comp.{output_name}"),
                reference_prob.get_val(f"comp.{output_name}") * annual_scale,
                rtol=1e-12,
            )


@pytest.mark.unit
def test_electrolyzer_large_slc_command_preserves_outputs(tech_config, plant_config, subtests):
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
    power_profile = np.full(n_timesteps, 32.0)
    reference_prob = _run_electrolyzer(plant_config, tech_config, power_profile)
    slc_plant_config = plant_config | {"system_level_control": {}}
    slc_prob = _run_electrolyzer(
        slc_plant_config,
        tech_config,
        power_profile,
        command_value=np.full(n_timesteps, 1e9),
    )

    with subtests.test("No command input is registered without SLC"):
        input_names = {name for name, _ in reference_prob.model.list_inputs(out_stream=None)}
        assert "comp.hydrogen_command_value" not in input_names

    with subtests.test("A nonbinding SLC command leaves every output unchanged"):
        reference_outputs = {
            name: reference_prob.get_val(name).copy()
            for name, _ in reference_prob.model.list_outputs(out_stream=None)
        }
        slc_outputs = {
            name: slc_prob.get_val(name).copy()
            for name, _ in slc_prob.model.list_outputs(out_stream=None)
        }
        assert reference_outputs.keys() == slc_outputs.keys()
        for output_name in reference_outputs:
            np.testing.assert_array_equal(slc_outputs[output_name], reference_outputs[output_name])
