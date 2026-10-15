"""Run script for the data center example.

Runs two grid-connected data center configurations driven by the same hourly
AI training compute load profile:

- ``data_center.yaml``: the simple data center model, where electricity demand is
  the compute load scaled by an electrical efficiency plus a proportional cooling load.
- ``data_center_pue_wue.yaml``: the PUE/WUE data center model, where PUE and WUE are
  looked up from the IECC climate zone of the site and the selected cooling configuration.
"""

import os

from h2integrate import EXAMPLE_DIR, H2IntegrateModel, load_yaml


os.chdir(EXAMPLE_DIR / "38_data_center")

# Hourly compute load profile (MW) for an AI training workload
compute_load_profile = load_yaml("compute_load_profile.yaml")["hourly_power_MW"]

# Simple data center model
h2i_simple = H2IntegrateModel("data_center.yaml")
h2i_simple.setup()
h2i_simple.prob.set_val("data_center.compute_load_demand", compute_load_profile, units="MW")
h2i_simple.run()
h2i_simple.post_process()

# PUE/WUE data center model
h2i_pue_wue = H2IntegrateModel("data_center_pue_wue.yaml")
h2i_pue_wue.setup()
h2i_pue_wue.prob.set_val("data_center.compute_it_workload", compute_load_profile, units="MW")
h2i_pue_wue.run()
h2i_pue_wue.post_process()

dc_pue_wue = h2i_pue_wue.prob.model.plant.data_center.DataCenterPUEWUEPerformanceModel
print(
    f"PUE/WUE model: climate zone {dc_pue_wue.config.climate_zone}, "
    f"PUE = {dc_pue_wue.config.pue:.2f}, WUE = {dc_pue_wue.config.wue:.2f} L/kWh"
)

for name, h2i in [("Simple", h2i_simple), ("PUE/WUE", h2i_pue_wue)]:
    electricity = h2i.prob.get_val("grid_buy.electricity_out", units="MW").sum()
    water = h2i.prob.get_val("data_center.water_consumed", units="galUS/h").sum()
    lcoc = h2i.prob.get_val("finance_subgroup_compute_load.LCOC", units="USD/(MW*h)")[0]
    print(
        f"{name} model: grid electricity = {electricity / 1e3:,.1f} GWh/yr, "
        f"water = {water / 1e6:,.1f} Mgal/yr, LCOC = ${lcoc:,.2f}/MWh"
    )
