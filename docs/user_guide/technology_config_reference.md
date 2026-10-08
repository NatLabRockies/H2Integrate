# Technology Configuration Reference

The technology configuration declares each technology, its model classes, and model-specific
inputs. It is referenced from the top-level configuration with `technology_config`. The schema is
maintained in [`tech_schema.yaml`](../../h2integrate/core/inputs/tech_schema.yaml), and
[`populate_tech_yaml`](populate_tech_yaml.md) can generate model input templates.

## Technology entries

Each key under `technologies` is a user-chosen technology name. Model class names are specified
under their respective model sections:

| Field | Purpose |
|---|---|
| `performance_model.model` | Registered performance model class. Required by the technology schema. |
| `cost_model.model` | Registered cost model class when the technology has a cost model. Some registered models are explicitly cost-free. |
| `control_strategy.model` | Optional controller class for technology-level control. |
| `dispatch_rule_set.model` | Rule class used by heuristic Pyomo dispatch. Optimized dispatch does not use this field. |
| `finance_model.model` | Optional technology-level finance model. |
| `model_location` | Optional source path for a custom performance, cost, or finance model. |
| `finance_model.group` | Name of the plant finance group that receives the technology-specific finance model. |

The performance, cost, control, dispatch-rule, and finance sections contain a `model` field; put
model parameters under `model_inputs`, not alongside `model`.

## Model inputs

`model_inputs` may contain:

- `shared_parameters`: values shared by at least two model roles.
- `performance_parameters`: performance-model configuration.
- `cost_parameters`: cost-model configuration.
- `financial_parameters`: technology finance-model configuration.
- `control_parameters`: technology controller configuration.

The accepted fields in each parameter section depend on the selected model. The model documentation
and generated templates are the sources for those model-specific values. For dispatch rule wiring,
see [Pyomo Controllers](../control/technology_level_control/pyomo_controllers.md); for technology
finance groups, see [Specifying Finance Parameters](specifying_finance_parameters.md).
