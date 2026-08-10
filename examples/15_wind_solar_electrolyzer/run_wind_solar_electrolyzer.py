from h2integrate import H2IntegrateModel


# Create a H2Integrate model
model = H2IntegrateModel("15_wind_solar_electrolyzer.yaml")

# Run the model
model.run()

model.post_process()

# Compare three ways of financing the hydrogen produced by the same physical plant:
#   Approach A ("same finance model"): wind + solar + electrolyzer financed together.
#   Approach B ("upstream LCOE feedstock"): the electrolyzer buys electricity as a
#       generic feedstock priced at the wind + solar LCOE.
#   Approach C ("grid buy"): the electrolyzer buys electricity through a grid
#       interconnection priced at the wind + solar LCOE.
# Approaches B and C should both give an identical result for LCOH, which should be
# close to the LOCH in Approach A.
lcoe = model.prob.get_val("finance_subgroup_electricity.LCOE", units="USD/kW/h")[0]
lcoh_integrated = model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0]
lcoh_feedstock = model.prob.get_val(
    "finance_subgroup_hydrogen_elec_feedstock.LCOH", units="USD/kg"
)[0]
lcoh_grid_buy = model.prob.get_val("finance_subgroup_hydrogen_elec_grid_buy.LCOH", units="USD/kg")[
    0
]

print(f"Upstream electricity LCOE:                      {lcoe:.4f} USD/kWh")
print(f"LCOH - A: wind + solar + electrolyzer together: {lcoh_integrated:.4f} USD/kg")
print(f"LCOH - B: electrolyzer + LCOE feedstock:        {lcoh_feedstock:.4f} USD/kg")
print(f"LCOH - C: electrolyzer + grid buy at LCOE:      {lcoh_grid_buy:.4f} USD/kg")
