from pathlib import Path

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml, load_driver_yaml


this_dir = EXAMPLE_DIR / "13_dispatch_for_electrolyzer"
tech_config = load_tech_yaml(this_dir / "tech_config.yaml")
plant_config = load_plant_yaml(this_dir / "plant_config.yaml")
driver_config = load_driver_yaml(this_dir / "driver_config.yaml")

# modify all the output folders to be full filepaths
driver_config["general"]["folder_output"] = str(Path(this_dir / "outputs").absolute())
tech_config["technologies"]["distributed_wind_plant"]["model_inputs"]["performance_parameters"][
    "cache_dir"
] = this_dir / "cache"

input_config = {
    "plant_config": plant_config,
    "technology_config": tech_config,
    "driver_config": driver_config,
}

h2i = H2IntegrateModel(input_config)

h2i.setup()

electrolyzer_capacity_MW = 60
h2i.prob.set_val("battery.electricity_demand", 0.1 * electrolyzer_capacity_MW, units="MW")
h2i.prob.set_val("elec_load_demand.electricity_demand", electrolyzer_capacity_MW, units="MW")

h2i.run()

h2i.post_process(print_results=False, summarize_sql=True)

lcoe_gen = h2i.prob.get_val("finance_subgroup_generated_electricity.LCOE", units="USD/(MW*h)")[0]
lcoe_sys = h2i.prob.get_val("finance_subgroup_electrical_system.LCOE", units="USD/(MW*h)")[0]
lcoe_load = h2i.prob.get_val("finance_subgroup_electrical_load.LCOE", units="USD/(MW*h)")[0]
lcoh = h2i.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0]
