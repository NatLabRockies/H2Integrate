"""
Wind and Hydrogen Electrolysis O&M
==================================

Thumbnail Alt Text.

Longer Description.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


h2i = H2IntegrateModel(EXAMPLE_DIR / "10_electrolyzer_om/electrolyzer_om.yaml")

# Run the model
h2i.run()

h2i.post_process()
