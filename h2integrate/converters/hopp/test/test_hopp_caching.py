import os
import shutil
from pathlib import Path

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
