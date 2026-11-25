"""
Wind & Direct Ocean Capture Power Splitting
===========================================

Short Description.

Longer Description.
"""

from h2integrate import EXAMPLE_DIR, H2IntegrateModel


# Create a H2Integrate model with power splitter
h2i_model = H2IntegrateModel(
    EXAMPLE_DIR / "17_splitter_wind_doc_h2/offshore_plant_splitter_doc_h2.yaml"
)

# Run the model
h2i_model.run()

# Post-process the results
h2i_model.post_process()
