# Plant Configuration Reference

The plant configuration describes site locations, simulation time, technology connections, and
system-level finance. It is referenced from the top-level configuration with `plant_config`. See
[Defining Sites and Connecting Resources](defining_sites_and_resources.md) for resource-specific
examples, and the [Technology Configuration Reference](technology_config_reference.md) and
[Driver Configuration Reference](driver_config_reference.md) for the other input files.

## Top-level fields

| Field | Purpose |
|---|---|
| `name`, `description` | Identify and describe the plant configuration. |
| `sites` | Named sites with latitude, longitude, optional elevation, and named resource models. |
| `plant` | Plant lifetime and simulation time settings. |
| `technology_interconnections` | Connections between technologies and optional transport components. |
| `site_to_tech_connections` | Connections from site data or resource outputs to technology inputs. |
| `tech_to_dispatch_connections` | Connections from technologies to dispatch rules or dispatch controllers. |
| `system_level_control` | Optional system-level controller configuration. |
| `finance_parameters` | Finance groups, subgroups, and cost-year adjustment settings. |

The plant schema currently validates the fields documented in
[`plant_schema.yaml`](../../h2integrate/core/inputs/plant_schema.yaml). The model also reads
`tech_to_dispatch_connections` and `system_level_control`, but these two keys are not currently
declared in that schema; they are therefore code-supported configuration fields that schema
validation does not check.

## Sites

Each site is identified by a user-chosen key. Latitude and longitude are required; elevation is
optional. A site's `resources` mapping may contain multiple named resource models. Each resource
entry specifies a registered `resource_model` and its `resource_parameters`; the resource key is a
user-chosen name, not the model class name. Use `site_to_tech_connections` to connect site location
or resource data to technologies.

Resource models have model-specific data ranges and time-step requirements. Some API-backed wind
and solar resources support multiple years; see the [resource index](../resource/resource_index.md)
and the wind and solar resource pages.

## Plant lifetime and simulation

`plant.plant_life` is the project lifetime in years. `plant.simulation` controls the simulated
period and uses seconds for `dt`:

```yaml
plant:
  plant_life: 30
  simulation:
    dt: 3600
    n_timesteps: 8760
    start_time: "01/01 00:30:00"
    timezone: 0
```

`dt` and `n_timesteps` are required by the schema. The default `dt` is 3600 seconds and the
default `n_timesteps` is 8760. `start_time` and `timezone` are optional; timezone is the UTC offset
for the start time. Every performance model in the system must support the selected `dt`, and the
requested simulation period must be compatible with the connected resource data.

## Technology and site connections

`technology_interconnections` lists source, destination, commodity or stream, and optionally a
transporter. For example, `- [wind, battery, electricity, cable]` connects wind electricity to a
battery through a cable. See [Connecting Technologies](connecting_technologies.md) for connection
forms and [Transport Components](../technology_models/transport.md) for cable, pipe, combiner, and
splitter behavior.

`site_to_tech_connections` connects a named site or resource to a technology. Resource data is
typically connected with a three-element entry such as
`[site.wind_resource, wind, wind_resource_data]`; site coordinates can also be mapped to technology
inputs. The site guide covers the supported forms and resource variable names.

`tech_to_dispatch_connections` is used when dispatch rules need information from technologies
upstream of a dispatch controller. Each pair identifies a source technology and the technology
whose dispatch model consumes it. For example, optimized battery dispatch commonly connects both
the upstream generator and battery to the battery controller:

```yaml
tech_to_dispatch_connections:
  - [wind, battery]
  - [battery, battery]
```

Declare the corresponding rule models in `tech_config.yaml`; the
[Pyomo Controllers](../control/technology_level_control/pyomo_controllers.md) guide explains the
heuristic and optimized patterns.

## System-level control

When present, `system_level_control` enables a plant-level controller. The strategy-specific
parameters are documented with each controller in the [System-Level Control](../control/system_level_control/system_level_control.md)
guide. For example, a demand-following configuration identifies the strategy and demand technology:

```yaml
system_level_control:
  control_strategy: DemandFollowingControl
  demand_component: electrical_load_demand
  solver_options:
    solver_name: gauss_seidel
    max_iter: 20
    convergence_tolerance: 1.0e-6
```

## Finance parameters

`finance_parameters` contains `finance_groups`, `finance_subgroups`, and
`cost_adjustment_parameters`. Groups define finance models and their inputs; subgroups select
technologies, a commodity stream, and one or more groups for an analysis. Cost adjustment converts
model costs to `target_dollar_year` using `cost_year_adjustment_inflation`. See
[Specifying Finance Parameters](specifying_finance_parameters.md) for the finance-group structure.
