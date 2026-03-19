# Hydrogen Steam Methane Reformer (SMR) Model

This module implements performance and cost models for a steam methane reformer (SMR) hydrogen production plant. The model converts natural gas and electricity inputs into hydrogen output subject to plant capacity constraints and feedstock availability.

The implementation consists of two components:
1. `SteamMethaneReformerPerformanceModel` – calculates hydrogen production and energy consumption over time.
2. `SteamMethaneReformerCostModel` – computes capital and operating costs based on plant capacity and hydrogen production.

The model is designed to integrate with the `h2integrate` framework and follows the standard configuration and model structure used for performance and cost models.

## Model Overview

Steam methane reforming is a thermochemical process where methane reacts with steam to produce hydrogen and carbon monoxide, followed by water-gas shift reactions to increase hydrogen yield.

The simplified representation used in this model assumes:
- Hydrogen production is limited by:
    - SMR rated capacity
    - Natural gas availability
    - Electricity availability
- Energy consumption is modeled using constant intensity parameters:
    - Natural gas consumption per kg of hydrogen
    - Electricity consumption per kg of hydrogen
- Hydrogen demand may be specified and unmet demand is tracked.
