# H2Integrate contributor and agent guidance

This file captures repository-wide conventions. Follow more specific instructions in the
directory being changed and preserve established behavior unless the task requires otherwise.

## Project conventions

- H2Integrate is a Python scientific-modeling framework built around OpenMDAO. Prefer clear,
  maintainable code; favor readability unless a more efficient approach is clearly justified.
- Keep changes focused. Separate unrelated formatting-only changes from behavior changes.
- Use descriptive `lowercase_with_underscores` names and add type hints to function parameters and
  return values. Use NumPy arrays for array data rather than Python lists.
- Keep units out of names exposed through OpenMDAO `add_input()`/`add_output()`; OpenMDAO handles
  unit conversion. Include units in internal variable names where helpful (for example,
  `length_m`).
- Follow existing package/module organization and reuse the relevant base class, shared fixtures,
  configuration patterns, and helpers rather than introducing parallel abstractions.

## Technology and model conventions

- Model classes normally implement OpenMDAO's `initialize()`, `setup()`, and `compute()` lifecycle.
  Select the appropriate H2Integrate base class and define required model attributes as described
  in `docs/developer_guide/adding_a_new_technology.md`.
- Register each available model with `@register` from `h2integrate.core.supported_models`; place
  the decorator immediately above the class definition. The registered name is part of the YAML
  interface, so do not change it casually.
- Use an attrs configuration class (`@define(kw_only=True)`) based on the appropriate existing
  config class. Name model-specific config classes `{ModelName}Config`, validate inputs with the
  existing config mechanisms, and instantiate the config in `setup()`.
- Call `super().setup()` where required by the base class so standard OpenMDAO inputs and outputs
  are registered. Preserve units, port names, output contracts, and control behavior.

## Python style and checks

- Target Python 3.13 and a maximum line length of 100 characters. Follow PEP 8 and the local Ruff
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
  in the working tree.
- For tests involving examples, follow the existing temporary-copy pattern in
  `examples/test/test_all_examples.py` rather than modifying checked-in example outputs.

## Documentation and docstrings

- Update relevant user/developer documentation and docstrings when behavior, configuration,
  model interfaces, or examples change. Keep explanations clear and concise, and keep examples
  executable and consistent with the current API.
- Use Google-style docstrings for functions, methods, and classes. Describe purpose, important
  behavior, arguments, return values, and exceptions as applicable; include type hints as well.
  For configuration classes, document fields in an `Attributes:` section. OpenMDAO docs may use
  the configured sections such as `Inputs:`, `Outputs:`, `Options:`, `Behavior:`, and
  `Side Effects:` where they clarify the component contract.
- Add new pages to `docs/_toc.yml` and use the
  established MyST Markdown/Sphinx patterns. Executable notebooks should be maintained as MyST
  Markdown; Jupytext commands are documented in `docs/CONTRIBUTING.md`.
- Treat `docs/_build/` and `docs/_autosummary/` as generated artifacts; edit their source pages,
  configuration, templates, or generators instead.

## Scope and references

For model-specific implementation and testing details, consult `docs/developer_guide/`, especially
`coding_guidelines.md`, `technology_model_types.md`, `adding_a_new_technology.md`, and `testing.md`.
For contribution and documentation workflow details, see `docs/CONTRIBUTING.md`.
