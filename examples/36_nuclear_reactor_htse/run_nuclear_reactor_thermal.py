import numpy as np
import matplotlib.pyplot as plt

from h2integrate.core.file_utils import load_yaml
from h2integrate.core.h2integrate_model import H2IntegrateModel


# load config and update htse refurb profile
config = load_yaml("nuclear_reactor_thermal_htse.yaml")
plant_config = load_yaml(config["plant_config"])
plant_life = plant_config["plant"]["plant_life"]
tech_config = load_yaml(config["technology_config"])

refurb = np.zeros(plant_life)
refurb[3::4] = 1
tech_config["technologies"]["htse"]["model_inputs"]["capital_items"]["refurb"] = refurb

config["technology_config"] = tech_config

h2i = H2IntegrateModel(config)

# generate N2 diagram
# om.n2(h2i.prob)

# Run and process the model
h2i.run()

h2i.post_process()
# expected water kg/h 4,347.8261
# generate plots of the output

e_nuclear = h2i.prob.get_val("nuclear.annual_electricity_produced", units="TW*h/year")[0]
e_htse = h2i.prob.get_val("htse.electricity_demand", units="TW*h/year")[0]
e_sold = h2i.prob.get_val("grid_sell.annual_electricity_sold", units="TW*h/year")[0]

heat_nuclear = np.sum(h2i.prob.get_val("nuclear.heat_out", units="GW"))
heat_htse = np.sum(h2i.prob.get_val("htse.heat_demand", units="GW"))

h2_htse = h2i.prob.get_val("htse.annual_hydrogen_produced", units="kt/year")[0]

# Print levelized cost outputs for each finance model/subgroup
lcoe_electricity = h2i.prob.get_val("finance_subgroup_electricity.LCOE", units="USD/(MW*h)")[0]
lcoh_hydrogen = h2i.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0]

print(f"LCOE (electricity finance subgroup): {lcoe_electricity:.2f} USD/MWh")
print(f"LCOH (hydrogen finance subgroup): {lcoh_hydrogen:.4f} USD/kg")

# Prepare data for bar charts
labels = ["Nuclear Plant", "HTSE Plant", "Grid Sold"]
electricity = [e_nuclear, e_htse, e_sold]

heat_labels = ["Nuclear Plant", "HTSE Plant"]
heat = [heat_nuclear, heat_htse]

h2_labels = ["HTSE Plant"]
h2 = [h2_htse]

fig, axs = plt.subplots(1, 3, figsize=(15, 5))

# Electricity bar chart: Nuclear Generation (left), Stacked HTSE+Grid (right)
bar_width = 0.6
x = np.arange(2)

# Bar 0: Total Nuclear Generation
axs[0].bar([0], [e_nuclear], color="deepskyblue", width=bar_width, label="Nuclear generation")

# Bar 1: Stacked HTSE + Grid Sold
axs[0].bar([1], [e_sold], color="green", width=bar_width, label="Sold to grid")
axs[0].bar([1], [e_htse], color="orange", width=bar_width, label="HTSE demand", bottom=e_sold)

axs[0].set_xticks([0, 1])
axs[0].set_xticklabels(["Produced", "Used"])
axs[0].set_ylabel("Annual Energy (TW*h/year)")
axs[0].set_title("Electricity")
axs[0].set(ylim=[0, 10])
axs[0].legend(ncol=2, frameon=False)

# Heat bar chart
axs[1].bar(heat_labels, heat, color=["red", "purple"])
axs[1].set_ylabel("Annual Heat (GWh/year)")
axs[1].set_title("Heat")

# H2 bar chart
axs[2].bar(h2_labels, h2, color=["gold"])
axs[2].set_ylabel("Annual Hydrogen (kt/year)")
axs[2].set_title("Hydrogen")

plt.tight_layout()
plt.show()
