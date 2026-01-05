import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import ROOT_DIR
from h2integrate.converters.hydrogen.geologic.simple_natural_geoh2 import (
    NaturalGeoH2PerformanceModel,
)
from h2integrate.converters.hydrogen.geologic.aspen_surface_processing import (
    AspenGeoH2SurfaceCostModel,
    AspenGeoH2SurfacePerformanceModel,
)


@fixture
def plant_config():
    plant = {
        "plant_life": 10,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }

    return {"plant": plant, "site": {"latitude": 32.34, "longitude": -98.27}}


@fixture
def geoh2_subsurface_well():
    plant = {
        "plant_life": 10,
        "simulation": {
            "dt": 3600,
            "n_timesteps": 8760,
            "start_time": "01/01/1900 00:30:00",
            "timezone": 0,
        },
    }

    plant_config_dict = {"plant": plant, "site": {"latitude": 32.34, "longitude": -98.27}}

    subsurface_perf_config = {
        "shared_parameters": {
            "borehole_depth": 300,
            "well_diameter": "small",
            "well_geometry": "vertical",
        },
        "performance_parameters": {
            "rock_type": "peridotite",
            "grain_size": 0.01,
            "use_prospectivity": False,
            "site_prospectivity": 0.7,
            "wellhead_h2_concentration": 95,
            "initial_wellhead_flow": 4000,
            "gas_reservoir_size": 1000000,
        },
    }
    tech_config_dict = {"model_inputs": subsurface_perf_config}
    subsurface_comp = NaturalGeoH2PerformanceModel(
        plant_config=plant_config_dict,
        tech_config=tech_config_dict,
        driver_config={},
    )
    return subsurface_comp


@fixture
def aspen_geoh2_config():
    model_inputs = {
        "shared_parameters": {"refit_coeffs": False, "curve_input_fn": "aspen_results.csv"},
        "performance_parameters": {
            "size_from_wellhead_flow": True,
            "max_flow_in": 0,
            "perf_coeff_fn": "aspen_perf_coeffs.csv",
        },
        "cost_parameters": {
            "cost_year": 2022,
            "cost_from_fit": True,
            "custom_capex": 0,
            "custom_opex": 0,
            "cost_coeff_fn": "aspen_cost_coeffs.csv",
            "op_labor_rate": 69.52,
            "overhead_rate": 0.5,
            "electricity_price": 0.0832,
            "water_price": 0.0,
        },
    }
    return {"model_inputs": model_inputs}


def test_aspen_geoh2_performance(subtests, plant_config, geoh2_subsurface_well, aspen_geoh2_config):
    prob = om.Problem()
    perf_comp = AspenGeoH2SurfacePerformanceModel(
        plant_config=plant_config,
        tech_config=aspen_geoh2_config,
        driver_config={},
    )

    well_group = prob.model.add_subsystem("well", om.Group())
    well_group.add_subsystem("perf", geoh2_subsurface_well, promotes=["*"])

    tech_group = prob.model.add_subsystem("geoh2", om.Group())
    tech_group.add_subsystem("perf", perf_comp, promotes=["*"])

    prob.model.connect("well.wellhead_gas_out", "geoh2.wellhead_gas_in")
    prob.model.connect("well.wellhead_h2_concentration_mol", "geoh2.wellhead_h2_concentration_mol")

    prob.setup()
    prob.run_model()

    with subtests.test("Well hydrogen production"):
        assert (
            pytest.approx(np.mean(prob.model.get_val("well.hydrogen_out", units="kg/h")), rel=1e-6)
            == 603.4286677531819
        ), 1e-6


def test_aspen_geoh2_performance_cost(
    subtests, plant_config, geoh2_subsurface_well, aspen_geoh2_config
):
    expected_capex = 1795733.55
    expected_opex = 4567464
    expected_varopex = 984842.53

    prob = om.Problem()
    perf_comp = AspenGeoH2SurfacePerformanceModel(
        plant_config=plant_config,
        tech_config=aspen_geoh2_config,
        driver_config={},
    )
    cost_comp = AspenGeoH2SurfaceCostModel(
        plant_config=plant_config,
        tech_config=aspen_geoh2_config,
        driver_config={},
    )

    well_group = prob.model.add_subsystem("well", om.Group())
    well_group.add_subsystem("perf", geoh2_subsurface_well, promotes=["*"])

    tech_group = prob.model.add_subsystem("geoh2", om.Group())
    tech_group.add_subsystem("perf", perf_comp, promotes=["*"])
    tech_group.add_subsystem("cost", cost_comp, promotes=["*"])

    prob.model.connect("well.wellhead_gas_out", "geoh2.wellhead_gas_in")
    prob.model.connect("well.wellhead_h2_concentration_mol", "geoh2.wellhead_h2_concentration_mol")

    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.model.get_val("geoh2.CapEx"), rel=1e-6) == expected_capex
    with subtests.test("OpEx"):
        assert pytest.approx(prob.model.get_val("geoh2.OpEx"), rel=1e-6) == expected_opex
    with subtests.test("VarOpEx"):
        assert pytest.approx(prob.model.get_val("geoh2.VarOpEx")[0], rel=1e-6) == expected_varopex


def test_aspen_geoh2_refit_coeffs(
    subtests, plant_config, geoh2_subsurface_well, aspen_geoh2_config
):
    input_dir = ROOT_DIR / "converters" / "hydrogen" / "geologic" / "inputs"
    perf_out_fname = "aspen_perf_coeffs_test.csv"
    cost_out_fname = "aspen_cost_coeffs_test.csv"

    aspen_geoh2_config["model_inputs"]["shared_parameters"].update({"refit_coeffs": True})
    aspen_geoh2_config["model_inputs"]["performance_parameters"].update(
        {"perf_coeff_fn": perf_out_fname}
    )
    aspen_geoh2_config["model_inputs"]["cost_parameters"].update({"cost_coeff_fn": cost_out_fname})

    prob = om.Problem()
    perf_comp = AspenGeoH2SurfacePerformanceModel(
        plant_config=plant_config,
        tech_config=aspen_geoh2_config,
        driver_config={},
    )
    cost_comp = AspenGeoH2SurfaceCostModel(
        plant_config=plant_config,
        tech_config=aspen_geoh2_config,
        driver_config={},
    )

    well_group = prob.model.add_subsystem("well", om.Group())
    well_group.add_subsystem("perf", geoh2_subsurface_well, promotes=["*"])

    tech_group = prob.model.add_subsystem("geoh2", om.Group())
    tech_group.add_subsystem("perf", perf_comp, promotes=["*"])
    tech_group.add_subsystem("cost", cost_comp, promotes=["*"])

    prob.model.connect("well.wellhead_gas_out", "geoh2.wellhead_gas_in")
    prob.model.connect("well.wellhead_h2_concentration_mol", "geoh2.wellhead_h2_concentration_mol")

    prob.setup()
    prob.run_model()

    with subtests.test("Well hydrogen production"):
        assert (
            pytest.approx(prob.model.get_val("well.hydrogen_out", units="kg/h"), rel=1e-6)
            == 603.4286677531819
        ), 1e-6

    with subtests.test("Refit Performance Coeff File"):
        perf_out_fpath = input_dir / perf_out_fname
        assert perf_out_fpath.exists()

    with subtests.test("Refit Cost Coeff File"):
        cost_out_fpath = input_dir / cost_out_fname
        assert cost_out_fpath.exists()

    # Remove refit coefficient files
    cost_out_fpath.unlink()
    perf_out_fpath.unlink()
