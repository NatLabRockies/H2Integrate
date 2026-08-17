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

## Testing

Use subtests to separate distinct behavior or state transitions within a longer test. When several
assertions verify one behavior, group them in a single subtest instead of creating one subtest per
assertion. This keeps tests readable while preserving useful failure context.

## Misc. development guidelines

- use Google style for docstrings
- use numpy instead of lists for arrays
- use type hints for function arguments and return values
