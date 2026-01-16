"""Comparing three different iron electrowinning technologies

This script runs an end-to-end iron production system (including the mine) and compares the
levelized cost of sponge_iron across three different iron electrowinning technologies to see
how their costs compare:
    - Aqueous Hydroxide Electrolysis (AHE)
    - Molten Salt Electrolysis (MSE)
    - Molten Oxide Electrolysis (MOE)

New users may find it helpful to look at the tech_config.yaml (particularly the iron_plant) to see
how the technologies were set up, as well as the  plant_config.yaml (particularly the
technology_interconnections) to see how the technologies were connected.

"""

from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create H2Integrate model
model = H2IntegrateModel("27_iron_electrowinning.yaml")

# Define the electrowinning types as a list
electrolysis_types = ["ahe", "mse", "moe"]
lcois = []

for electrolysis_type in electrolysis_types:
    # Set the technology config value directly
    model.technology_config["technologies"]["iron_plant"]["model_inputs"]["shared_parameters"][
        "electrolysis_type"
    ] = electrolysis_type
    model.setup()  # re-setup the model after changing config
    model.run()
    model.post_process()
    lcois.append(
        float(
            model.model.get_val("finance_subgroup_sponge_iron.price_sponge_iron", units="USD/kg")[0]
        )
    )

# Compare the LCOIs from each electrowinning type
print("Levelized Cost of Iron (LCOI) by Electrowinning Type:")
for electrolysis_type, lcoi in zip(electrolysis_types, lcois):
    print(f"  {electrolysis_type.upper()}: ${lcoi:,.2f} per kg of sponge iron")
