"""
Small Modular Nuclear Reactor for Methanol
==========================================

Thumbnail Alt Text.

Longer Description.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


# Create an H2I model
example_path = EXAMPLE_DIR / "03_methanol/smr/"
h2i = H2IntegrateModel("03_smr_methanol.yaml")

# Run the model
h2i.run()

h2i.post_process()
