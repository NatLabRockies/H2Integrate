---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: h2integrate
  language: python
  name: python3
---

(reliability)=
# Reliability Modeling

Inspired by the work in NLR's [WOMBAT](https://github.com/NLRWindSystems/WOMBAT) model for
operations and maintenance, the
[`PerformanceReliability`](#h2integrate.reliability.models.PerformanceReliability) provides the
means to model simplified component-level failures and maintenance events to capture component-
and system-level availability.

The [`PerformanceReliability`](#h2integrate.reliability.models.PerformanceReliability) is intended
to be integrated into a performance model by applying multiplying the `availability` by the
appropriate production or demand array.

To ensure stability of results, the seeding of the random generator is fixed for repeatable results
across simulations.

(reliability:availability)=
## Availability Types

The `availability_type` allows the user to compute the system-level availability as if the system
is a collection of systems ("fractional") or a series of components within the system ("minimum").

### Fractional Availability

The fractional availability is essentially a simplified version of an energy-based availability
calculation that does not account for any required connections between components, e.g., array
cable failures would not impact a wind farm's availability as it would in reality.

$availability_{system} = \frac{1}{N} \sum_{i=0}^{N} availability_i$ where $i$ is a
component, or individual system when modeling a collection of systems (e.g., wind farm).

Because the fractional availability is an average among components/individual systems, if both
a maintenance and failure model are defined, they must have the same number of components (unlike
with minimum availability).

### Minimum Availability

The minimum availability is simply the minimum component availability for both or either (when not
modeling both) of the failure and maintenance model.

(reliability:reliability)=
## Reliability Models

Currently, a Weibull distribution and fixed interval downtime model exist to mimic the behaviors
of failure and maintenance events in WOMBAT, respectively, however either or both could be modeled
with the same type of distribution.

Unlike WOMBAT, this model does not consider partial downtimes, repair equipment, or materials costs,
but does allow users to model varying distributions of [downtime](#reliability:downtime).

Since H2Integrate typically defines an annual simulation period, a `burn_in` factor is enabled to
allow users to skip an arbitrary number of years ahead instead of repeatedly modeling the first
year of system's life. For more details, please visit the
[reliability API documentation](#h2integrate.reliability).

Individual reliability models can also be used independent of the `PerformanceReliability` model,
so `system_availability` and `component_availability` metrics are calculated according to each
model's `availability_type`.

Available models:

- [BaseReliability](#h2integrate.reliability.models.BaseReliability)
- [WeibullReliability](#h2integrate.reliability.models.WeibullReliability)
- [FixedIntervalReliability](#h2integrate.reliability.models.FixedIntervalReliability)

(reliability:downtime)=
## Downtime Models

To accompany the modeling of downtime events (reliability models), there are models to either
randomly sample downtime durations or use a fixed-duration downtime.

Available models:

- [BaseDowntime](#h2integrate.reliability.models.BaseDowntime)
- [FixedDowntime](#h2integrate.reliability.models.FixedDowntime)
- [UniformDowntime](#h2integrate.reliability.models.UniformDowntime)
- [LogNormalDowntime](#h2integrate.reliability.models.LogNormalDowntime)

(reliability:example)=
## Usage

### Standalone Example

```{code-cell} ipython3
from h2integrate.reliability import PerformanceReliability

config = {
    "simulation": {"dt": 3600, "n_timesteps": 8760},
    "use_reliability": True,
    "burn_in": 6.5,
    "availability_type": "fractional",
    "failure_model": "WeibullReliability",
    "maintenance_model": "FixedIntervalReliability",
    "failure_parameters": {
        "scale": 0.5,
        "shape": 1,
        "n_components": 3,
        "downtime": {
            "model": "FixedDowntime",
            "hours": 5,
            "n_components": 3,
        },
    },
    "maintenance_parameters":{
        "frequency": [0.25, 1, 4],
        "downtime": {
            "model": "UniformDowntime",
            "min_hours": 2,
            "max_hours": 5,
            "n_components": 3,
        },
    },
}

reliability = PerformanceReliability.from_dict(config)
reliability.run()

print(f"Failure-based availability: {reliability.failures.system_availability.sum() / reliability.failures.system_availability.size:.2%}")
print(f"Maintenance-based availability: {reliability.maintenance.system_availability.sum() / reliability.maintenance.system_availability.size:.2%}")
print(f"System-level availability: {reliability.availability.sum() / reliability.availability.size:.4%}")
```

### Integration In the Natural Gas Model

Below is the application of the `PerformanceReliability` model to the `NaturalGasPerformanceModel`

During an initialization a reliability model should be defaulted to None.

```python
class NaturalGasPerformanceModel(PerformanceModelBaseClass):
    def initialize(self):
        ...
        self.reliability_model = None
```

During setup,

1) the simulation details must be extracted from the `plant_config`,
2) the `use_reliability` configuration should control the creation and application of the
   reliability modeling, and
3) the model should be created

```python
    def setup(self):
        ...

        if use_reliability := "reliability" in self.options["tech_config"]["model_inputs"]:
            plant_simulation_config = self.options["plant_config"]["plant"]["simulation"]
            simulation_config = {
                "simulation": {
                    "dt": plant_simulation_config.get("dt", 3600),
                    "n_timesteps": plant_simulation_config.get("n_timesteps", 8760),
                },
            }
            config = self.options["tech_config"]["model_inputs"]["reliability"]
            use_reliability = config.get("use_reliability", use_reliability)
            self.reliability_model = PerformanceReliability.from_dict(config | simulation_config)
        self.use_reliability = use_reliability
        ...

```

During compute the model should be run and the availability applied at the demand stage to correctly
impact the actual production of energy from the natural gas plant.

```python
    def compute(self):
        ...
        natural_gas_demand = electricity_command_value * heat_rate_mmbtu_per_mwh
        if self.use_reliability:
            self.reliability_model.run()
            natural_gas_demand * self.reliability_model.availability
        ...
```

To apply the above example to the natural gas model, the following "reliability" dictionary should
be added to a "tech_config.yaml" file, such as in
`H2Integrate/examples/16_natural_gas/tech_config.yaml`.

```yaml
...
technologies:
  ...
  natural_gas_plant:
    ...
    model_inputs:
      ...
      reliability:
        use_reliability: True
        availability_type: fractional
        burn_in: 6.5
        failure_model: WeibullReliability
        maintenance_model: FixedIntervalReliability
        failure_parameters:
          scale: 0.5
          shape: 1
          n_components: 3
          downtime:
            model: FixedDowntime
            hours: 5
            n_components: 3
        maintenance_parameters:
          frequency: [0.25, 1, 4]
          downtime:
            model: UniformDowntime
            min_hours: 2
            max_hours: 5
            n_components: 3
...
```
