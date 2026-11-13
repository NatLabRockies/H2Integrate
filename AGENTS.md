# H2Integrate contributor and agent guidance

This file captures repository-wide conventions. Follow more specific instructions in the
directory being changed and preserve established behavior unless the task requires otherwise.

## Project conventions

- H2Integrate is a Python scientific-modeling framework built around OpenMDAO. Prefer clear,
  maintainable code; favor readability unless a more efficient approach is clearly justified.
- Keep changes focused. Separate unrelated formatting-only changes from behavior changes.
- Name model-specific attrs configuration classes `{ModelName}Config` and instantiate them in `setup()`.
  Preserve registered model names because they are part of the YAML interface. Retain shared base
  configurations when intentional, but use a model-specific configuration when fields or semantics differ.
- Use NumPy arrays for array data rather than Python lists.
- Keep units out of names exposed through OpenMDAO `add_input()`/`add_output()`; OpenMDAO handles
  unit conversion. Include units in internal variable names where helpful (for example,
  `length_m`).
- Follow existing package/module organization and reuse the relevant base class, shared fixtures,
  configuration patterns, and helpers rather than introducing parallel abstractions. H2Integrate has
  8 model categories that you should stick to: control, converter, core, finance, reliability, resource,
  storage, and transporter. If the addition does not fit into one of these categories, ask where it should fit.
- Use the `_baseclass.py` suffix for modules that define base classes so they are easy to find.
- Do not run pre-commit hooks unless the user explicitly requests it; the user handles hook execution.

## Technology and model conventions

- Model classes normally implement OpenMDAO's `initialize()`, `setup()`, and `compute()` lifecycle.
  Select the appropriate H2Integrate base class and define required model attributes as described
  in `docs/developer_guide/adding_a_new_technology.md`.
- Use H2Integrate's performance and cost base classes rather than inheriting directly from OpenMDAO
  components. Prefer an existing category-specific base class when applicable; create a new intermediate
  base class only when multiple models share inputs, outputs, or methods.
- Register each available model with `@register` from `h2integrate.core.supported_models`; place
  the decorator immediately above the class definition. Use the class name as its registration name
  unless an explicit alias is needed.
- Use an attrs configuration class (`@define(kw_only=True)`) based on the appropriate existing
  config class. Name model-specific config classes `{ModelName}Config`, validate inputs with the
  existing config mechanisms, and instantiate the config in `setup()`.
- Call `super().setup()` where required by the base class so standard OpenMDAO inputs and outputs
  are registered and inherited setup runs before model-specific configuration and additional inputs
  or outputs are registered. Preserve units, port names, output contracts, and control behavior.
- Call `super().initialize()` where required by the base class so that standard OpenMDAO `options` are registered.
- Ensure each model defines or inherits accurate `_time_step_bounds` in seconds and `_simulation_duration_bounds`
  in years. Widen these bounds only when the model supports the additional time steps or simulation durations.
- Set performance models' `commodity`, `commodity_rate_units`, and `commodity_amount_units` in `initialize()`
  or before `super().setup()` runs, so the base class can register standard production outputs.
- Set or inherit the appropriate `_control_classifier` for each performance model: `"fixed"`, `"flexible"`,
  `"dispatchable"`, `"storage"`, or `"feedstock"`, according to how it participates in system-level control.
- In flexible performance models, call `self.apply_curtailment(outputs)` after writing raw production to
  `outputs[f"{self.commodity}_out"]`. Dispatchable models handle command values through their own internal
  logic instead.
- Use `merge_shared_inputs(model_inputs, kind)` to combine shared and model-specific parameters, then
  validate with `BaseConfig.from_dict(..., strict=True)` so duplicate and unknown keys are rejected.
- Model each technology using performance, cost, control, and optional technology-specific finance models.
  Keep these in separate classes by default; combine roles only when required by the code being wrapped.
  Use framework-provided controllers where applicable. Rely on system-level finance models for general financial
  analysis, adding technology-specific finance models for financial modeling choices or calculations unique to
  the technology.

## Python style and checks

- Target Python 3.11 and a maximum line length of 100 characters. Follow PEP 8 and the local Ruff
  and isort configuration rather than reformatting unrelated code by hand.
- Keep YAML formatting consistent with the configured yamlfix hook. Some test/example input YAML
  paths are intentionally excluded; do not normalize those files without understanding their
  purpose.

## Tests

- Run test commands from the repository root in the development environment. Every test must have
  at least one recognized marker: `unit`, `regression`, `integration`, or `hpc`; unmarked tests
  fail collection.
- Choose tests to match the change: unit tests for isolated behavior and edge cases, regression
  tests for stable model results, and integration tests for interactions among components. New
  functionality should be covered by the relevant categories.
- Use subtests to group distinct behaviors or state transitions in a longer test; keep assertions
  for one behavior together. Prefer reusable, parameterized fixtures from nearby `conftest.py`
  files. Use the `temp_dir` fixture for generated files and caches so tests do not leave artifacts
  in the working tree. For each test, add a short comment stating the purpose.
- For tests involving examples, follow the existing temporary-copy pattern in
  `examples/test/test_all_examples.py` rather than modifying checked-in example outputs.
- Reuse existing test fixtures for common setup and teardown. Prefer parameterizing reusable
  fixtures over duplicating setup or creating many single-use fixtures.

## Documentation and docstrings

- Update relevant user/developer documentation and docstrings when behavior, configuration,
  model interfaces, or examples change. Keep explanations clear and concise, and keep examples
  executable and consistent with the current API.
- Use Google-style docstrings for functions, methods, and classes. Describe purpose, important
  behavior, arguments, return values, and exceptions as applicable; include type hints as well.
  For configuration classes, document fields in an `Attributes:` section. For functions and methods,
  include the `Args` and `Returns` sections in the docstrings, along with type hints. OpenMDAO docs may use
  the configured sections such as `Inputs:`, `Outputs:`, `Options:`, `Behavior:`, and
  `Side Effects:` where they clarify the component contract.
- Add new pages to `docs/_toc.yml` and use the
  established MyST Markdown/Sphinx patterns. Executable notebooks should be maintained as MyST
  Markdown; Jupytext commands are documented in `docs/CONTRIBUTING.md`.
- Treat `docs/_build/` and `docs/_autosummary/` as generated artifacts; edit their source pages,
  configuration, templates, or generators instead.
- Defer documentation updates until the user confirms code work is complete, approves all code changes, and all
  required tests pass. Only then update affected documentation. Do not build the documentation unless the user explicitly requests it.
- Append "(AI)" to inline comments written by an agent (not docstrings)
- Prefer technical clarity over marketing tone and avoid filler phrases

## Plan approval
- For every user request, first present a clear, concise plan and wait for explicit user approval before making
  any code changes. If the plan materially changes, obtain approval for the revised plan before proceeding.

# Github interaction
- Agents should never push, pull or fetch, or commit code changes.

## Scope and references

For model-specific implementation and testing details, consult `docs/developer_guide/`, especially
`coding_guidelines.md`, `technology_model_types.md`, `adding_a_new_technology.md`, and `testing.md`.
For contribution and documentation workflow details, see `docs/CONTRIBUTING.md`.
