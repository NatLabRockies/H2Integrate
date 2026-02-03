import os
import shutil
from pathlib import Path

import numpy as np
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml
from h2integrate.converters.hopp.hopp_wrapper import HOPPComponent


@fixture
def plant_config():
    plant_cnfg = load_plant_yaml(EXAMPLE_DIR / "25_sizing_modes" / "plant_config.yaml")
    return plant_cnfg


@fixture
def tech_config():
    os.chdir(EXAMPLE_DIR / "25_sizing_modes")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "25_sizing_modes" / "tech_config.yaml")
    hopp_tech_config = tech_config["technologies"]["hopp"]

    return hopp_tech_config


def test_hopp_wrapper_outputs(subtests, plant_config, tech_config):
    tech_config["model_inputs"]["performance_parameters"]["enable_caching"] = False
    tech_config["model_inputs"]["performance_parameters"]["hopp_config"]["technologies"]["wind"][
        "num_turbines"
    ] = 4
    prob = om.Problem()

    hopp_perf = HOPPComponent(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", hopp_perf, promotes=["*"])
    prob.setup()
    prob.run_model()
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])
    commodity = "electricity"
    commodity_amount_units = "kW*h"
    commodity_rate_units = "kW"

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
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


def test_hopp_wrapper_cache_filenames(subtests, plant_config, tech_config):
    cache_dir = EXAMPLE_DIR / "25_sizing_modes" / "test_cache"

    # delete cache dir if it exists
    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    tech_config["model_inputs"]["performance_parameters"]["enable_caching"] = True
    tech_config["model_inputs"]["performance_parameters"]["cache_dir"] = cache_dir

    # Run hopp and get cache filename
    prob = om.Problem()

    hopp_perf = HOPPComponent(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
    )
    prob.model.add_subsystem("perf", hopp_perf, promotes=["*"])
    prob.setup()
    prob.run_model()

    cache_filename_init = list(Path(cache_dir).glob("*.pkl"))

    # Modify something in the hopp config and check that cache filename is different
    tech_config["model_inputs"]["performance_parameters"]["hopp_config"]["config"][
        "simulation_options"
    ].pop("cache")

    # Run hopp and get cache filename
    prob = om.Problem()

    hopp_perf = HOPPComponent(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
    )
    prob.model.add_subsystem("perf", hopp_perf, promotes=["*"])
    prob.setup()
    prob.run_model()

    cache_filename_new = [
        file for file in Path(cache_dir).glob("*.pkl") if file not in cache_filename_init
    ]

    with subtests.test("Check unique filename with modified config"):
        assert len(cache_filename_new) > 0

    # Delete cache files and the testing cache dir
    shutil.rmtree(cache_dir)
