import numpy as np
import pytest
import openmdao.api as om

from h2integrate.finances.finances import AdjustedCapacityFactorComp


@pytest.fixture
def plant_config(n_timesteps):
    plant = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "dt": 3600,
                "n_timesteps": n_timesteps,
            },
        },
    }
    return plant


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [8760])
def test_adjusted_cf_comp(plant_config, subtests):
    rng = np.random.default_rng(seed=0)
    electricity_input = rng.random(8760) * 1e3

    prob = om.Problem()
    comp = AdjustedCapacityFactorComp(plant_config=plant_config, commodity_type="electricity")
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    ivc = om.IndepVarComp()
    ivc.add_output("electricity_produced", val=np.zeros(8760), units="kW")
    prob.model.add_subsystem("ivc", ivc, promotes=["*"])

    prob.setup()
    prob.set_val("ivc.electricity_produced", val=electricity_input, units="kW")
    prob.run_model()

    with subtests.test("Check rated_electricity_production calc"):
        assert (
            pytest.approx(
                prob.model.get_val("comp.rated_electricity_production", units="kW"), rel=1e-6
            )
            == electricity_input.mean()
        )

    with subtests.test("Check capacity factor"):
        assert np.all(prob.model.get_val("comp.capacity_factor", units="unitless")) == 1.0

    with subtests.test("Capacity factor length"):
        assert len(prob.model.get_val("comp.capacity_factor", units="unitless")) == 30


@pytest.mark.unit
@pytest.mark.parametrize(
    "n_timesteps,annual_extrapolation_method,expected_capacity_factor",
    [
        (2 * 8760, "tile", [0.5, 1.0, 0.5, 1.0]),
        (2 * 8760, "final_sim_value", [0.5, 1.0, 1.0, 1.0]),
        (2 * 8760, "time_averaged_sim_value", [0.5, 1.0, 0.75, 0.75]),
        (8760 + 4380, "tile", [0.5, 1.0, 0.5, 1.0]),
        (8760 + 4380, "final_sim_value", [0.5, 1.0, 1.0, 1.0]),
        (8760 + 4380, "time_averaged_sim_value", [0.5, 1.0, 2.0 / 3.0, 2.0 / 3.0]),
    ],
)
def test_adjusted_cf_comp_preserves_annual_profile(
    plant_config,
    n_timesteps,
    annual_extrapolation_method,
    expected_capacity_factor,
    subtests,
):
    plant_config["plant"]["plant_life"] = 4
    plant_config["plant"]["simulation"]["annual_extrapolation_method"] = annual_extrapolation_method
    rated_production = 300.0  # kW
    production_timeseries = np.concatenate(
        (np.full(8760, rated_production / 2.0), np.full(n_timesteps - 8760, rated_production))
    )

    problem = om.Problem()
    component = AdjustedCapacityFactorComp(
        plant_config=plant_config,
        commodity_type="electricity",
    )
    problem.model.add_subsystem("component", component, promotes=["*"])

    independent = om.IndepVarComp()
    independent.add_output("electricity_produced", val=np.zeros(n_timesteps), units="kW")
    problem.model.add_subsystem("independent", independent, promotes=["*"])

    problem.setup()
    problem.set_val("independent.electricity_produced", production_timeseries, units="kW")
    problem.run_model()

    with subtests.test("Check rated electricity production"):
        assert problem.get_val("component.rated_electricity_production", units="kW")[
            0
        ] == pytest.approx(rated_production)

    with subtests.test("Check capacity factor"):
        np.testing.assert_allclose(
            problem.get_val("component.capacity_factor", units="unitless"),
            expected_capacity_factor,
        )


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [2 * 8760])
def test_adjusted_cf_comp_requires_method_for_multiyear_extrapolation(plant_config, n_timesteps):
    plant_config["plant"]["plant_life"] = 4
    production_timeseries = np.concatenate((np.full(8760, 100.0), np.full(8760, 300.0)))
    problem = om.Problem()
    component = AdjustedCapacityFactorComp(plant_config=plant_config, commodity_type="electricity")
    problem.model.add_subsystem("component", component, promotes=["*"])

    independent = om.IndepVarComp()
    independent.add_output("electricity_produced", val=production_timeseries, units="kW")
    problem.model.add_subsystem("independent", independent, promotes=["*"])

    problem.setup()
    with pytest.raises(ValueError, match="annual_extrapolation_method is required"):
        problem.run_model()


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [2 * 8760])
def test_adjusted_cf_comp_subgroup_method_overrides_plant_method(plant_config, n_timesteps):
    plant_config["plant"]["plant_life"] = 4
    plant_config["plant"]["simulation"]["annual_extrapolation_method"] = "tile"
    production_timeseries = np.concatenate((np.full(8760, 100.0), np.full(8760, 300.0)))

    problem = om.Problem()
    component = AdjustedCapacityFactorComp(
        plant_config=plant_config,
        commodity_type="electricity",
        annual_extrapolation_method="final_sim_value",
    )
    problem.model.add_subsystem("component", component, promotes=["*"])

    independent = om.IndepVarComp()
    independent.add_output("electricity_produced", val=np.zeros(n_timesteps), units="kW")
    problem.model.add_subsystem("independent", independent, promotes=["*"])

    problem.setup()
    problem.set_val("independent.electricity_produced", production_timeseries, units="kW")
    problem.run_model()

    np.testing.assert_allclose(
        problem.get_val("component.capacity_factor", units="unitless"),
        [1.0 / 3.0, 1.0, 1.0, 1.0],
    )


@pytest.mark.unit
@pytest.mark.parametrize("n_timesteps", [8760])
def test_adjusted_cf_comp_uses_integer_dt_like_plant_validation(plant_config, n_timesteps):
    # A fractional dt is truncated by plant validation and the base classes, so 8760 steps are
    # exactly one year; using the raw dt would split them into two segments and require a method.
    plant_config["plant"]["simulation"]["dt"] = 3600.5
    production_timeseries = np.full(n_timesteps, 100.0)

    problem = om.Problem()
    component = AdjustedCapacityFactorComp(plant_config=plant_config, commodity_type="electricity")
    problem.model.add_subsystem("component", component, promotes=["*"])

    independent = om.IndepVarComp()
    independent.add_output("electricity_produced", val=production_timeseries, units="kW")
    problem.model.add_subsystem("independent", independent, promotes=["*"])

    problem.setup()
    problem.run_model()

    np.testing.assert_allclose(
        problem.get_val("component.capacity_factor", units="unitless"), np.ones(30)
    )
