"""
CO2 Hydrogenation for Methanol
==============================

Short Description.

Longer Description.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


# Create an H2I model
example_path = EXAMPLE_DIR / "03_methanol/co2_hydrogenation/"
h2i = H2IntegrateModel(example_path / "03_co2h_methanol.yaml")

# Run the model
h2i.run()

h2i.post_process()
