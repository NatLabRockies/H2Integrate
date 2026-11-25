"""
Single Site Steel Production
============================

Thumbnail Alt Text.

Longer Description.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


config_path = EXAMPLE_DIR / "21_iron_examples/iron_cmu/dri/single_site_steel.yaml"
model = H2IntegrateModel(config_path)
model.setup()
model.run()
model.post_process()
