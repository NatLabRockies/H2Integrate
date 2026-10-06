# Diesel Generator Model

The diesel generator model simulates electricity generation from diesel combustion. The model calculates electricity output based on diesel input and plant heat rate, along with comprehensive cost modeling that includes capital expenses, operating expenses, and fuel costs.

To use this model, specify `"DieselGeneratorPerformanceModel"` as the performance model and `"DieselGeneratorCostModel"` as the cost model.

## Performance Parameters

The performance model requires the following parameters:

- `system_capacity_kw` (required): Rated capacity of the natural gas plant in kW.
- `heat_rate_gal_per_mwh` (required): Heat rate of the diesel generator in gallons/MWh. This represents the amount of fuel energy required to produce one MWh of electricity. Lower values indicate higher efficiency.

Optional parameter:
- `electricity_set_point` (optional): Defaults to the `system_capacity` but can be set to a particular set point profile.

The model implements the relationship:

$$
\text{Electricity Output (MW)} = \frac{\text{Diesel Input (gals/h)}}{\text{Heat Rate (gals/MWh)}}
$$

The `electricity_out` is limited by the system capacity and the available diesel fuel feedstock.

## Cost Parameters

The cost model calculates capital and operating costs based on the following parameters:

- `capex` (required): Capital cost per unit capacity in $/kW. This includes all equipment, installation, and construction costs.

- `fopex` (required): Fixed operating expenses per unit capacity in \$/kW/year. This includes fixed O&M costs that don't vary with generation.

- `vopex` (required): Variable operating expenses per unit generation in \$/MWh. This includes variable O&M costs that scale with electricity generation.

- `heat_rate` (required): Heat rate in gallons/MWh, used for fuel cost calculations.

- `cost_year` (required): Dollar year corresponding to input costs.
