# Coding guidelines

This document outlines the coding guidelines for H2Integrate development.

## Documentation development

The key to making H2Integrate more user-friendly is to have clear and concise documentation.
This includes docstrings for functions and classes, as well as high-level documentation for the tool itself.
We should also have a clear way to document the expected methods and attributes of classes so that users can develop their own models.

## Variable naming conventions

When naming variables, use a clear and verbose name with lowercase letters and underscores to separate words.

If the variable is exposed to OpenMDAO via the `add_input` or `add_output` methods, you should not include units in the variable name.
This is because OpenMDAO automatically handles converting units for inputs and outputs, and including units in the variable name can lead to confusion or errors when connecting variables between components.
If the variable is not exposed to OpenMDAO, you should include units in the name for clarity, e.g. `length_m`, `initial_tank_volume_m3`.

## Model and configuration naming

When a model uses an attrs configuration class, name the configuration class
after the model class by appending `Config`. For example:

```python
@define(kw_only=True)
class ExamplePerformanceModelConfig(BaseConfig):
	"""Configuration for ``ExamplePerformanceModel``."""

	...
```

The model should instantiate that class in `setup()`. Keep the registered model
name (the class name, or the `name` passed to `@register`) unchanged when
renaming or clarifying a configuration
class, because that model name is part of the YAML interface. Models that
intentionally share a base configuration may retain a base config class, but
the model-specific class should still be used when the fields or semantics
differ. The `populate_tech_yaml` utility recognizes the direct `{ModelName}Config`
convention and can also discover inherited or explicitly supplied config classes.

## Base class file naming

Modules that define base classes should use the `_baseclass.py` suffix, for example
`h2integrate/core/model_baseclass.py` or `h2integrate/storage/storage_baseclass.py`.
This keeps base classes easy to find by searching the code base for `baseclass`.

## Testing

Use subtests to separate distinct behavior or state transitions within a longer test. When several
assertions verify one behavior, group them in a single subtest instead of creating one subtest per
assertion. This keeps tests readable while preserving useful failure context.

## Misc. development guidelines

- use Google style for docstrings
- use numpy instead of lists for arrays
- use type hints for function arguments and return values

## Automated checks

Ruff and the other hooks in `.pre-commit-config.yaml` run on changed files locally and in CI.
Ruff enforces the configured rule sets in `pyproject.toml`.
The selected rules include:

- [`C901`](https://docs.astral.sh/ruff/rules/complex-structure/) limits McCabe complexity to 30.
- [`SIM101`](https://docs.astral.sh/ruff/rules/duplicate-isinstance-call/) combines repeated
  `isinstance` checks on the same value.
- [`PIE`](https://docs.astral.sh/ruff/rules/#flake8-pie-pie) and
  [`PYI`](https://docs.astral.sh/ruff/rules/#flake8-pyi-pyi) enable the respective Ruff rule
  families for general Python improvements and stub files.
- [`S110`](https://docs.astral.sh/ruff/rules/try-except-pass/) flags exception handlers that
  silently discard errors. [`BLE001`](https://docs.astral.sh/ruff/rules/blind-except/) flags broad
  exception handlers.

See the [Ruff rule reference](https://docs.astral.sh/ruff/rules/) for rule details.
`codespell` checks Markdown and reStructuredText documentation, and pre-commit rejects added files over 500 KB.
Pull-request CI also requires a `CHANGELOG.md` update, reports changed-line counts, rejects added files over 500 KB, and prevents adding files matched by `.gitignore` as generated artifacts.
Unit tests also verify that YAML examples name registered models and that registered model names appear in documentation; explicit allowlists identify existing exceptions.
