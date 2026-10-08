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

## Design variables, objective, and constraints

`design_variables` and `constraints` are grouped by technology or finance-subgroup name, then by
OpenMDAO variable name. Set `flag` to enable each entry and provide its `units`; design variables
may also specify bounds and scaling, while constraints require at least one of `lower`, `upper`, or
`equals`. The single `objective` identifies the full OpenMDAO variable name to minimize. To
maximize a result, minimize its negative using the objective's `ref` scaling as appropriate.

## Recorder

Set `recorder.flag` to enable an SQL recorder. The `file` name is written inside
`general.folder_output`; `overwrite_recorder` controls whether an existing file is replaced or a
unique suffix is used. `recorder_attachment` may be `driver` or `model` (the driver is recommended
for parallel runs).

| Field | Purpose |
|---|---|
| `includes` | Glob patterns selecting variables to record. Defaults to `['*']`. |
| `excludes` | Glob patterns to omit. Defaults to `['*resource_data']`, which avoids storing large, constant resource profiles. |
| `record_inputs`, `record_outputs`, `record_residuals` | Select component-level data. |
| `options_excludes` | Component option names to omit when attached to the model. |
| `record_desvars`, `record_objectives`, `record_constraints`, `record_derivative` | Select driver data; used when attached to the driver. |

The schema is maintained in [`driver_schema.yaml`](../../h2integrate/core/inputs/driver_schema.yaml).
See [Recording and Loading Data](recording_and_loading_data.md) for working recorder examples.
