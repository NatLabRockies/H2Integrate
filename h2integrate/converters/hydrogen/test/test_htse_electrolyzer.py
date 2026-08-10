import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.hydrogen.htse_electrolyzer import HTSECostModel, HTSEPerformanceModel


@fixture
def plant_config():
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }


@fixture
def htse_performance_params():
    return {
        "n_clusters": 25,
        "cluster_rating_MW": 1.0,
        "nominal_heat_required": 6.4,
        "nominal_electricity_required": 36.8,
        "turndown_ratio": 0.1,
        "uptime_hours_until_eol": 35040,
    }


@fixture
def htse_cost_params():
    return {
        "unit_capex": 1417.0,
        "cost_year": 2022,
    }


def _build_performance_problem(plant_config, performance_params):
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": performance_params,
        }
    }

    prob = om.Problem()
    perf_comp = HTSEPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("htse_perf", perf_comp, promotes=["*"])
    prob.setup()
    return prob


@pytest.mark.unit
def test_htse_performance_full_production(plant_config, htse_performance_params, subtests):
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
    nom_elec = htse_performance_params["nominal_electricity_required"]
    nom_heat = htse_performance_params["nominal_heat_required"]

    electrolyzer_size_kw = (
        htse_performance_params["n_clusters"]
        * htse_performance_params["cluster_rating_MW"]
        * 1000.0
    )
    rated_hydrogen_production = electrolyzer_size_kw / nom_elec

    # Supply exactly the heat and electricity demanded so the model runs at rated production
    heat_demand_kw = rated_hydrogen_production * nom_heat
    electricity_demand_kw = electrolyzer_size_kw

    prob = _build_performance_problem(plant_config, htse_performance_params)
    prob.set_val("heat_in", np.full(n_timesteps, heat_demand_kw), units="kW")
    prob.set_val("electricity_in", np.full(n_timesteps, electricity_demand_kw), units="kW")
    prob.run_model()

    hydrogen_out = prob.get_val("hydrogen_out", units="kg/h")

    with subtests.test("Hydrogen produced at rated capacity"):
        assert pytest.approx(hydrogen_out, rel=1e-6) == np.full(
            n_timesteps, rated_hydrogen_production
        )

    with subtests.test("Rated hydrogen production reported"):
        assert pytest.approx(prob.get_val("rated_hydrogen_production", units="kg/h")[0]) == (
            rated_hydrogen_production
        )

    with subtests.test("Installed HTSE size reported"):
        assert pytest.approx(prob.get_val("electrolyzer_size_mw", units="MW")[0]) == 25.0

    with subtests.test("Electricity demand equals installed electrical size"):
        assert pytest.approx(prob.get_val("electricity_demand", units="kW")) == (
            np.full(n_timesteps, electrolyzer_size_kw)
        )

    with subtests.test("Heat demand based on hydrogen demand"):
        assert pytest.approx(prob.get_val("heat_demand", units="kW")) == (
            np.full(n_timesteps, heat_demand_kw)
        )

    with subtests.test("Capacity factor is one at full production"):
        assert pytest.approx(prob.get_val("capacity_factor")) == np.ones(
            plant_config["plant"]["plant_life"]
        )

    with subtests.test("Efficiency is one when input matches demand"):
        assert pytest.approx(prob.get_val("efficiency")[0], rel=1e-6) == 1.0

    with subtests.test("Water consumption follows stoichiometry"):
        expected_water_gal = rated_hydrogen_production * (18.015 / 2.016) / 3.785411
        assert pytest.approx(prob.get_val("water_consumed", units="galUS/h"), rel=1e-6) == (
            np.full(n_timesteps, expected_water_gal)
        )

    with subtests.test("Annual hydrogen production"):
        assert pytest.approx(prob.get_val("annual_hydrogen_produced", units="kg/year")) == np.full(
            plant_config["plant"]["plant_life"], rated_hydrogen_production * n_timesteps
        )


@pytest.mark.unit
def test_htse_performance_turndown_shutoff(plant_config, htse_performance_params, subtests):
    n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]

    prob = _build_performance_problem(plant_config, htse_performance_params)
    # Provide electricity well below the turndown threshold and no heat
    prob.set_val("heat_in", np.zeros(n_timesteps), units="kW")
    prob.set_val("electricity_in", np.full(n_timesteps, 100.0), units="kW")
    prob.run_model()

    with subtests.test("Hydrogen production is zero below turndown"):
        assert pytest.approx(prob.get_val("hydrogen_out", units="kg/h")) == np.zeros(n_timesteps)

    with subtests.test("Total hydrogen produced is zero"):
        assert prob.get_val("total_hydrogen_produced", units="kg")[0] == pytest.approx(0.0)

    with subtests.test("Capacity factor is zero"):
        assert pytest.approx(prob.get_val("capacity_factor")) == np.zeros(
            plant_config["plant"]["plant_life"]
        )


@pytest.mark.unit
def test_htse_cost_model(plant_config, htse_cost_params, subtests):
    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": htse_cost_params,
        }
    }

    electrolyzer_size_mw = 25.0
    electrolyzer_size_kw = electrolyzer_size_mw * 1000.0

    prob = om.Problem()
    cost_comp = HTSECostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("htse_cost", cost_comp, promotes=["*"])
    prob.setup()

    prob.set_val("electrolyzer_size_mw", electrolyzer_size_mw, units="MW")
    prob.run_model()

    with subtests.test("Capital cost scales with installed size"):
        expected_capex = htse_cost_params["unit_capex"] * electrolyzer_size_kw
        assert pytest.approx(prob.get_val("CapEx", units="USD")[0], rel=1e-6) == expected_capex

    with subtests.test("Operating cost defaults to zero when fixed_opex omitted"):
        assert prob.get_val("OpEx", units="USD/year")[0] == pytest.approx(0.0)

    with subtests.test("Cost year is reported"):
        assert prob.get_val("cost_year") == htse_cost_params["cost_year"]


@pytest.mark.unit
def test_htse_cost_model_fixed_opex(plant_config, subtests):
    electrolyzer_size_mw = 25.0
    electrolyzer_size_kw = electrolyzer_size_mw * 1000.0

    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": {
                "unit_capex": 1417.0,
                "fixed_opex": 10.0,
            },
        }
    }

    prob = om.Problem()
    cost_comp = HTSECostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("htse_cost", cost_comp, promotes=["*"])
    prob.setup()
    prob.set_val("electrolyzer_size_mw", electrolyzer_size_mw, units="MW")
    prob.run_model()

    with subtests.test("Operating cost uses provided fixed_opex"):
        assert pytest.approx(prob.get_val("OpEx", units="USD/year")[0], rel=1e-6) == (
            10.0 * electrolyzer_size_kw
        )


@pytest.mark.unit
def test_htse_cost_model_fixed_capex_fallback(plant_config, subtests):
    electrolyzer_size_mw = 25.0
    electrolyzer_size_kw = electrolyzer_size_mw * 1000.0

    tech_config_dict = {
        "model_inputs": {
            "cost_parameters": {
                "unit_capex": 1417.0,
                "fixed_capex": 5.0,
            },
        }
    }

    prob = om.Problem()
    cost_comp = HTSECostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("htse_cost", cost_comp, promotes=["*"])
    prob.setup()
    prob.set_val("electrolyzer_size_mw", electrolyzer_size_mw, units="MW")
    prob.run_model()

    with subtests.test("fixed_capex populates fixed_opex when fixed_opex omitted"):
        assert pytest.approx(prob.get_val("OpEx", units="USD/year")[0], rel=1e-6) == (
            5.0 * electrolyzer_size_kw
        )
