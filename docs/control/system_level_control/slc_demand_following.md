(slc-demand-following)=
# Demand Following System Level Controller

The demand following controller, `DemandFollowingControl`, aims to fully meet the demand and does not have any inputs related to cost.

## Inputs and Outputs

The inputs for technologies classified as `curtailable`, `dispatchable`, and `storage` are:

- `f"{tech_name}_{tech_output_commodity}_out"`
- `f"{tech_name}_rated_{tech_output_commodity}_production"`

The inputs for technologies classified as `feedstock` are:
- `f"{tech_name}_{commodity}_out"`


The outputs for technologies classified as `curtailable`, `dispatchable`, or `storage` and *without a storage controller* are:
- `f"{tech_name}_{tech_output_commodity}_set_point"`

The outputs for technologies classified as `storage` that *have a storage controller* are:
- `f"{tech_name}_{tech_output_commodity}_demand"`

## Heterogenous Systems


## Limitations


## General Logic

First, control logic is as follows:
- For every technology classified as "curtailable", set the set-point as the rated commodity production of that technology. Subtract the commodity produced by the technology from the overall demand profile
- The remaining demand profile will be negative when the curtailable technologies produce more commodity than demanded and positive when the curtailable technologies produce less commodity than demanded. The remaining demand profile is divided by the number of storage technologies in the system to get the set point for each storage technology. This set point is negative to command the storage to charge, and positive to command the storage to discharge.
