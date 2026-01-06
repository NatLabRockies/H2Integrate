import os

import pytest

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml, load_driver_yaml


# Load the 'base' configs needed to create the H2I model
driver_config = load_driver_yaml(EXAMPLE_DIR / "25_sizing_modes" / "driver_config.yaml")
plant_config = load_plant_yaml(EXAMPLE_DIR / "25_sizing_modes" / "plant_config.yaml")
tech_config = load_tech_yaml(EXAMPLE_DIR / "25_sizing_modes" / "tech_config.yaml")
input_config = {
    "name": "H2Integrate_config",
    "system_summary": "hybrid plant containing ammonia plant and electrolyzer",
    "driver_config": driver_config,
    "plant_config": plant_config,
    "technology_config": tech_config,
}


def test_resize_by_max_feedstock(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "25_sizing_modes")

    # Create a H2Integrate model, modifying tech_config as necessary
    tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
        "size_mode"
    ] = "resize_by_max_feedstock"
    tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
        "flow_used_for_sizing"
    ] = "electricity"
    tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
        "max_feedstock_ratio"
    ] = 1.0
    input_config["technology_config"] = tech_config
    model = H2IntegrateModel(input_config)

    model.run()

    with subtests.test("Check electrolyzer size"):
        assert (
            pytest.approx(model.prob.get_val("electrolyzer.electrolyzer_size_mw")[0], rel=1e-3)
            == 1080
        )


def test_resize_by_max_commodity(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "25_sizing_modes")

    # Create a H2Integrate model, modifying tech_config as necessary
    tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
        "size_mode"
    ] = "resize_by_max_commodity"
    tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
        "flow_used_for_sizing"
    ] = "hydrogen"
    tech_config["technologies"]["electrolyzer"]["model_inputs"]["performance_parameters"][
        "max_commodity_ratio"
    ] = 1.0
    input_config["technology_config"] = tech_config
    plant_config["technology_interconnections"] = [
        ["hopp", "electrolyzer", "electricity", "cable"],
        ["electrolyzer", "ammonia", "hydrogen", "pipe"],
        ["ammonia", "electrolyzer", "max_hydrogen_capacity"],
    ]
    input_config["plant_config"] = plant_config
    model = H2IntegrateModel(input_config)

    model.run()

    with subtests.test("Check electrolyzer size"):
        assert (
            pytest.approx(model.prob.get_val("electrolyzer.electrolyzer_size_mw")[0], rel=1e-3)
            == 560
        )
