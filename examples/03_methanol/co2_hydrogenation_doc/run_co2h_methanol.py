"""
Direct Ocean Capture CO2 Hydrogenation for Methanol
===================================================

Thumbnail Alt Text.

Longer Description.
"""

from plot_co2h_methanol import plot_methanol

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


# Create an H2I model
example_path = EXAMPLE_DIR / "03_methanol/co2_hydrogenation_doc/"
h2i = H2IntegrateModel("03_co2h_methanol.yaml")

# Run the model
h2i.run()

h2i.post_process()

# Plot major in/out flows
plot_methanol(h2i.prob.model)
