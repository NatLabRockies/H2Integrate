from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create an H2I model for natural geologic hydrogen production
h2i_nat = H2IntegrateModel("04_geo_h2_natural.yaml")

# Run the model
h2i_nat.run()
h2i_nat.post_process()

import matplotlib.pyplot as plt


hydrogen_out = (
    h2i_nat.prob.model.plant.geoh2_well_subsurface.simple_natural_geoh2_performance.get_val(
        "hydrogen_out"
    )
)
plt.plot(hydrogen_out)
plt.xlabel("Time (hours)")
plt.ylabel("Wellhead Gas Flow (kg/h)")
plt.title("Wellhead Gas Flow Profile Over First Year")
plt.grid()
plt.show()


# Create an H2I model for stimulated geologic hydrogen production
h2i_stim = H2IntegrateModel("04_geo_h2_stimulated.yaml")

# Run the model
h2i_stim.run()
h2i_stim.post_process()
