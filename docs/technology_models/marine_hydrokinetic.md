# Marine Hydrokinetic (MHK) Models

H2I has several marine hydrokinetic (MHK) models for performance and costs. Marine and Hydrokinetic (MHK) technologies harness renewable energy from waves, tidal currents, ocean currents, and riverine flows to generate electricity.

Within H2I there are models for:
- [Run-Of-River Hydropower](run_of_river_hydro)
- [Tidal](tidal_performance)
- [MHK Costs](pysam_mhk_costs)

(pysam_mhk_costs)=
## PySAM MHK Cost Model
The **PySAM Marine Cost Model** estimates capital and operational costs for marine hydrokinetic (MHK) energy systems, including tidal and wave energy technologies. The model wraps the [PySAM MhkCosts module](https://nrel-pysam.readthedocs.io/en/main/modules/MhkCosts.html) implementation of the marine hydrokinetic cost model used in the [System Advisor Model (SAM)](https://sam.nlr.gov/). To use this model, specify `"PySAMMarineCostModel"` as the cost model.

The cost model leverages technology assumptions and cost structures developed through the U.S. Department of Energy [Reference Model Project](https://energy.sandia.gov/programs/renewable-energy/water-power/projects/reference-model-project-rmp/) for marine energy technologies. These reference models provide standardized system configurations and cost relationships for different MHK device types.

This component is implemented as an OpenMDAO-compatible cost model and can be integrated into larger hybrid energy system simulations.

### Model Overview

The model estimates:
- Capital expenditures (CapEx) for MHK devices and associated infrastructure
- Operational expenditures (OpEx) for maintenance and operations

Costs are derived using the PySAM MhkCosts module, which calculates costs for:
- Device structural and power take-off systems
- Mooring and foundation systems
- Installation and infrastructure
- Electrical systems
- Project development and financial costs
- Operations and maintenance

The final outputs are total installed capital cost and annual operating cost.

The model supports several reference technologies from the DOE Reference Model Project. Each reference model corresponds to cost relationships embedded in the PySAM cost library.

| Reference Model | Technology               |
| --------------- | ------------------------ |
| RM1             | Tidal Current Turbine    |
| RM2             | River Current Turbine    |
| RM3             | Wave Point Absorber      |
| RM5             | Oscillating Surge Flap   |
| RM6             | Oscillating Water Column |
