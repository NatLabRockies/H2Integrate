# Natural gas power plant model

The natural gas power plant model simulates electricity generation from natural gas combustion, suitable for both natural gas combustion turbines (NGCT) and natural gas combined cycle (NGCC) plants. The model calculates electricity output based on natural gas input and plant heat rate, along with comprehensive cost modeling that includes capital expenses, operating expenses, and fuel costs.

To use this model, specify `"NaturalGasPerformanceModel"` as the performance model and `"NaturalGasCostModel"` as the cost model.

## Performance Parameters

The performance model requires the following parameters:

- `system_capacity` (required): Rated capacity of the natural gas plant in MW.
- `heat_rate` (required): Heat rate of the natural gas plant in MMBtu/MWh. This represents the amount of fuel energy required to produce one MWh of electricity. Lower values indicate higher efficiency. Typical values:
  - **NGCC (Combined Cycle)**: 6-8 MMBtu/MWh (high efficiency)
  - **NGCT (Combustion Turbine)**: 10-14 MMBtu/MWh (lower efficiency, faster response)

Optional parameter:
- `electricity_demand` (optional): Defaults to the `system_capacity` but can be set to a particular demand profile.
  - See example `16_natural_gas` to see how missed load from the battery is set as the electricity demand for the natural gas plant.

The model implements the relationship:

$$
\text{Electricity Output (MW)} = \frac{\text{Natural Gas Input (MMBtu/h)}}{\text{Heat Rate (MMBtu/MWh)}}
$$

The `electricity_out` is limited by the system capacity and the available natural gas feedstock.

## Cost Parameters

The cost model calculates capital and operating costs based on the following parameters:

- `capex` (required): Capital cost per unit capacity in $/kW. This includes all equipment, installation, and construction costs. Typical values:
  - **NGCT**: 600-2000 $/kW (lower capital cost)
  - **NGCC**: 800-2400 $/kW (higher capital cost)

- `fopex` (required): Fixed operating expenses per unit capacity in \$/kW/year. This includes fixed O&M costs that don't vary with generation. Typical values: 5-15 \$/kW/year

- `vopex` (required): Variable operating expenses per unit generation in \$/MWh. This includes variable O&M costs that scale with electricity generation. Typical values: 1-5 \$/MWh

- `heat_rate` (required): Heat rate in MMBtu/MWh, used for fuel cost calculations.

- `cost_year` (required): Dollar year corresponding to input costs.
