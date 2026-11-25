"""
Tidal Power
===========

Thumbnail Alt Text.

Longer Description.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


# Create an H2I model
h2i = H2IntegrateModel(EXAMPLE_DIR / "31_tidal/tidal.yaml")

# Run the model
h2i.run()

# Post-process the results
h2i.post_process()
