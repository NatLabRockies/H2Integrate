# WOMBAT Electrolyzer O&M Model

The `WOMBATElectrolyzerModel` provides a detailed, simulation-based approach to estimating the operations and maintenance (O&M) costs and availability of hydrogen electrolyzers. This model leverages the [WOMBAT](https://github.com/WISDEM/WOMBAT) (Windfarm Operations and Maintenance cost-Benefit Analysis Tool) framework, originally developed for wind farm O&M analysis, and adapts it for hydrogen systems.

## What is WOMBAT?

WOMBAT is a discrete-event simulation tool designed to model the full lifecycle of O&M activities for energy systems. It tracks maintenance events, failures, repairs, and resource constraints, providing a realistic estimate of downtime, lost production, and O&M costs. By simulating both scheduled and unscheduled maintenance, WOMBAT captures the complexity of real-world operations, including compounding failures and limited servicing capacity.

Originally developed to evaluate O&M strategies for wind farms, WOMBAT was adapted to model hydrogen systems by integrating a centrally located electrolyzer supplied with energy from the hybrid plant’s electrical substation. The model computes accumulated downtime, its impact on hydrogen production, and the associated O&M expenses, closely mirroring real-world operations.

## Why use WOMBAT for electrolyzer O&M?

Traditional O&M cost estimates for electrolyzers often rely on simple availability factors or fixed OpEx percentages. These approaches do not capture the true variability and impact of maintenance events, especially as electrolyzer fleets scale up. By using WOMBAT, H2Integrate can:

- Simulate detailed maintenance schedules and random failures using Weibull-distributed time-to-failure, a proven approach in reliability modeling
- Account for both time-based and usage-based maintenance, with support for fixed intervals based on operational hours or calendar time
- Model the impact of downtime on hydrogen production, including compounding events like simultaneous failures or limited servicing capacity
- Provide more accurate, scenario-specific OpEx estimates based on simulated maintenance events, not just fixed percentages

WOMBAT’s scheduled and unscheduled maintenance models are informed by real-world data collection efforts. For unscheduled maintenance, time to failure is sampled from a Weibull distribution, as is common in wind turbine reliability modeling. Scheduled maintenance can be triggered by usage or the passage of time, and the model supports specifying first occurrence dates for more realistic scheduling.

## Model Structure: Integrating Performance and O&M

The `WOMBATElectrolyzerModel` builds on the existing `ECOElectrolyzerPerformanceModel`, which simulates PEM electrolyzer performance (hydrogen output, efficiency, etc.) based on plant and technology configuration. The WOMBAT model then modifies the performance outputs by simulating O&M events:

1. **Performance Calculation**: The base PEM model computes hydrogen output and efficiency for a given electricity input profile.
2. **O&M Simulation**: WOMBAT simulates maintenance and failure events, generating a time series of electrolyzer availability and O&M costs. The system model encapsulates subassemblies (collections of component models), each with their own failure and maintenance tasks, and coordinates repairs and status checking at the system level.
3. **Adjustment of Outputs**: The hydrogen output is scaled by the simulated availability, and OpEx is calculated based on actual maintenance events, not just a fixed percentage. This enables the model to capture the true impact of O&M on hydrogen production and costs.

This approach enables much more accurate and dynamic cost modeling, especially for scenarios with high utilization or challenging maintenance environments. The model can be used for a single 1 MW electrolyzer or scaled to larger systems by adjusting the input profiles and configuration.

```{note}
The `electrolyzer.yml` configuration file may include sections such as `turbines` and `substation` that do not appear directly relevant to electrolyzer modeling. This is because WOMBAT currently assumes a certain system setup inherited from its wind O&M origins. These sections are required for the model to run, even if their parameters are not used in the electrolyzer context.
```

## Example: Using the WOMBAT Electrolyzer Model

To use the WOMBAT electrolyzer model in H2Integrate, configure your `tech_config.yaml` to use `WOMBATElectrolyzerModel` for both the performance and cost models.
An example is shown below:

### tech_config.yaml (excerpt)

```yaml
technologies:
  electrolyzer:
    performance_model:
      model: "WOMBATElectrolyzerModel"
    cost_model:
      model: "WOMBATElectrolyzerModel"
    model_inputs:
      shared_parameters:
        location: "onshore"
        electrolyzer_capex: 1295
        # ...other parameters...
        library_path: "resource_files/wombat_library"
      performance_parameters:
        n_clusters: 1
        cluster_rating_MW: 10 #MW
```

For a full example, see the `10_electrolyzer_om` example in the `examples/` directory.

```{note}
The provided electrolyzer library and associated O&M costs in this model are illustrative and do not represent real-world or proprietary data. Actual O&M costs and failure rates can vary significantly depending on technology, vendor, and operating environment. Because we cannot publish actual numbers, users are strongly encouraged to conduct their own research and data collection to ensure the model inputs reflect their specific use case and the most current industry information.
```

```{note}
The WOMBAT model is designed to simulate a single electrolyzer unit for one year. If you need to model multiple units or longer time periods, you may need to adjust the H2Integrate source code accordingly.
```

## Key Outputs

The WOMBAT electrolyzer model provides the following outputs:

- **hydrogen_out**: Hourly hydrogen production, adjusted for simulated availability
- **total_hydrogen_produced**: Total annual hydrogen output (kg)
- **percent_hydrogen_lost**: Percentage of hydrogen lost due to O&M downtime
- **OpEx**: Annual operational expenditure, based on simulated maintenance events
- **CapEx**: Capital expenditure (from configuration)
- **electrolyzer_availability**: Simulated time-based availability
