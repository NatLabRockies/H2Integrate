from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create an H2I model for natural geologic hydrogen production
h2i_nat = H2IntegrateModel("04_geo_h2_natural.yaml")

# Run the model
h2i_nat.run()
h2i_nat.post_process()

import matplotlib.pyplot as plt


hydrogen_out = h2i_nat.prob.model.plant.geoh2_well_subsurface.NaturalGeoH2PerformanceModel.get_val(
    "annual_hydrogen_produced", units="t/year"
)
start_year = (
    h2i_nat.prob.model.plant.finance_subgroup_h2.hydrogen_finance_default.params.analysis_start_year
)
years = range(start_year, start_year + len(hydrogen_out))
plt.plot(years, hydrogen_out)
plt.xlabel("Year")
plt.ylabel("Hydrogen Production (tonne per annum)")
plt.title("Hydrogen Production over Well Lifetime")
plt.grid()
plt.show()


# Create an H2I model for stimulated geologic hydrogen production
h2i_stim = H2IntegrateModel("04_geo_h2_stimulated.yaml")

# Run the model
h2i_stim.run()
h2i_stim.post_process()
