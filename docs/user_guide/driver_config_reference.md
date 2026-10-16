# Driver Configuration Reference

The driver configuration controls output files, optional OpenMDAO reports, analysis drivers,
design variables, objectives, constraints, and recording. It is referenced from the top-level
configuration with `driver_config`.

## General options

| Field | Default | Purpose |
|---|---:|---|
| `general.folder_output` | `output` | Directory for generated output and recorder files. |
| `general.create_om_reports` | `true` | Create OpenMDAO reports, including N2 diagrams. Set to `false` to disable them. |

## Analysis driver

The `driver` mapping may contain `optimization` or `parameter_sweep`. At most one driver's `flag`
can be true. If neither is enabled, the model runs once using the configured values. Optimization
settings include the solver, tolerance, iteration limit, derivative options, and solver-specific
options. The `parameter_sweep` block selects a generator and its inputs, such as `num_samples`,
`levels`, or a CSV `filename`. See [Design Optimization](design_optimization_in_h2i.md) and
[Parameter Sweeps](parameter_sweep_in_h2i.md) for workflows and examples.

An optimization driver config selects a solver, then lists design variables, an objective, and
optionally constraints. This is the driver config from
[Example 5](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/05_wind_h2_opt):

```{literalinclude} ../../examples/05_wind_h2_opt/driver_config.yaml
:language: yaml
:linenos: true
```

A parameter sweep uses the `parameter_sweep` block instead. This is the driver config from
[Example 22](https://github.com/NatLabRockies/H2Integrate/tree/develop/examples/22_site_doe), which
evaluates the cases listed in a CSV file (`csvgen` generator):

```{literalinclude} ../../examples/22_site_doe/driver_config.yaml
:language: yaml
:linenos: true
```

## Design variables, objective, and constraints

`design_variables` and `constraints` are grouped by technology or finance-subgroup name, then by
OpenMDAO variable name. Set `flag` to enable each entry and provide its `units`; design variables
may also specify bounds and scaling, while constraints require at least one of `lower`, `upper`, or
`equals`. The single `objective` identifies the full OpenMDAO variable name to minimize.

The top-level key under `design_variables` and `constraints` is a technology name from
`tech_config.yaml` (or a finance subgroup name from `plant_config.yaml`), and the key beneath it is
the variable name. Together they form the full OpenMDAO variable name, `{technology}.{variable}`. For
example, this design variable is `electrolyzer.n_clusters`, and this constraint is
`electrical_load_demand.percent_load_missed`:

```yaml
design_variables:
  electrolyzer:  # technology name in tech_config.yaml
    n_clusters:  # variable name
      flag: true
      lower: 2.
      upper: 40.
      units: unitless
constraints:
  electrical_load_demand:
    percent_load_missed:
      flag: true
      upper: 5.
      units: percent
```

To find the correct variable name, run the model once and look at the results table that is printed
at the end of the run. The `prom_name` column lists the full variable names, and the technology and
variable name are the parts before and after the first period (see
[Postprocessing Results](postprocessing_results.md)). Design variables are inputs to a model, such as
the parameters you set under `model_inputs` in `tech_config.yaml`, and constraints are usually model
outputs. [Design Optimization](design_optimization_in_h2i.md) has more detail.

The objective is given as the full variable name, with an optional `ref`. The `ref` is the reference
value that the driver uses to scale the objective to a magnitude of 1, which can help the optimizer
converge. The driver always minimizes, so to maximize a result, use a negative `ref`. In the example
below, the `ref` value of 10.0 means that the optimizer scales the objective so that an LCOH of 10.0
is treated as 1. This allows the user to control the scaling of the objective and helps provide a
more well-posed optimization problem.

```yaml
objective:
  name: finance_subgroup_hydrogen.LCOH
  ref: 10.0  # use a negative value, such as -1.0, to maximize instead
```

## Recorder

Set `recorder.flag` to enable an SQL recorder. The `file` name is written inside
`general.folder_output`; `overwrite_recorder` controls whether an existing file is replaced or a
unique suffix is used. `recorder_attachment` may be `driver` or `model` (the driver is recommended
for parallel runs).

```yaml
recorder:
  flag: true
  file: cases.sql
  overwrite_recorder: true
  recorder_attachment: driver
  includes: ['*']
  excludes: ['*resource_data']
```

| Field | Purpose |
|---|---|
| `includes` | Glob patterns selecting variables to record. Defaults to `['*']`. |
| `excludes` | Glob patterns to omit. Defaults to `['*resource_data']`, which avoids storing large, constant resource profiles. |
| `record_inputs`, `record_outputs`, `record_residuals` | Select component-level data. |
| `options_excludes` | Component option names to omit when attached to the model. |
| `record_desvars`, `record_objectives`, `record_constraints`, `record_derivative` | Select driver data; used when attached to the driver. |

```{note}
The `excludes` supersede the `includes`. A variable that matches both an `includes` pattern and
an `excludes` pattern is not recorded. For example, with `includes: ['*']` and
`excludes: ['*resource_data']`, everything except the resource data is recorded.
```

The schema is maintained in [`driver_schema.yaml`](../../h2integrate/core/inputs/driver_schema.yaml).
See [Recording and Loading Data](recording_and_loading_data.md) for working recorder examples.
