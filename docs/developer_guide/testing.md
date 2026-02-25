# Writing and Running Tests

Ideally 3 types of tests should be written for new functionality: unit, regression, and
integration, which will be covered later in this section. Each of these test types should cover as
much of the written code as possible. When adding new tests they should be decorated with one of
the following to allow for code maintainers to track test coverage
for the varying test types: `@pytest.mark.unit`, `@pytest.mark.regression`, or
`pytest.mark.integration`. In practice this looks like:

```python
@pytest.mark.unit
def test_simple_numeric_conversion():
    ... # test contents
```

For further information on how to write or run a test, please see the
[`pytest` documentation](https://docs.pytest.org/en/stable/index.html), which outlines many
useful features for both writing and running tests.

When running tests (or building the docs) OpenMDAO produces a significant number of outputs files
and folders, which can be cleaned up using `openmdao clean`. This will prompt you to confirm every
folder, so if you don't need to review the OpenMDAO output files, they can be universally wiped
without prompts using the `-f` flag. Use `--help` for further usage instructions.

## Chunking Lengthy or Complex Tests

At times these tests can be lengthy because many checks could be required in a single test function,
so it can be helpful to chunk these into subtests to allow the whole test to be run and fail at the end
rather than failing at the first unsuccessful check. This is especially helpful when testing around
complex logic and other subtests can provide insight into the nature of the failure. For these we
utilize the [subtests](https://docs.pytest.org/en/stable/how-to/subtests.html) functionality. The
example below will show the most basic usage to get started.

```python
# h2integrate/core/test/test_utilities.py
@pytest.mark.unit
def test_BaseConfig(subtests):
    """Tests the BaseConfig class."""

    with subtests.test("Check basic passing inputs"):
        demo = BaseDemoModel({"x": 1})
        assert demo.config.x == 1
        assert demo.config.y == "y"

    with subtests.test("Check allowed inputs overload"):
        demo = BaseDemoModel({"x": 1, "z": 2})
        assert demo.config.x == 1
        assert demo.config.y == "y"

    ... # rest of the test
```

## Unit Tests

Unit tests should test the correctness of the code in isolation from the rest of the system.
At a minimum, this involves testing data handling, utility methods, setup, and error handling. Care
should also be taken to test around the edges of the program being written to ensure code can't
silently fail by producing erroneous results or failing unexpectedly.

Run `pytest -m unit` to run only the unit test suite or `pytest -m not-unit` to skip the unit tests.

An example of a unit test is in the example below where there is only a validation of the location
of the output directory and subdirectory, and not the contents of those files.

:::{literalinclude} ../../h2integrate/resource/utilities/test/test_resource_file_tools.py
:start-at: @pytest.mark.unit
:end-at: assert output_dir == expected_output_dir
:::

## Regression Tests

In an analysis-focused code base, regression tests should test the results of running the code to
ensure changes made do not alter expected results. These should not encapsulate more than the focal
system if it can be helped.

Run `pytest -m regression` to run only the regression test suite or `pytest -m not-regression` to
skip the regression tests.

An example of a regression test is in the example below where the model's outputs are checked
for stability with some tolerance.

:::{literalinclude} ../../h2integrate/converters/co2/marine/test/test_doc.py
:start-at: @pytest.mark.regression
:end-at: assert_near_equal(total_tank_volume_m3
:::

## Integration Tests

Integration tests should test the integration of the new code into other systems in the code base.
For a new model or technology, this will run it in conjunction with other technologies or models
and, similar to regression tests, will test the results of that code, ensuring the combination of
multiple components does not cause unexpected changes in any of the involved components.

An example would be to test that a model configuration that contributed to a publication always
produces the same results, ensuring the legitimacy of those results and the underlying modeled
systems.

Run `pytest -m integration` to run only the integration test suite or `pytest -m not-integration`
to skip the integration tests.

For examples of integration tests, please see the `examples/test/test_all_examples.py` module
where multiple components are combined to test the models outputs for stability when using tools
in conjunction with each other.

## Test coverage

To test the code coverage of the testing suite, we use the
[`pytest-cov`](https://pytest-cov.readthedocs.io/en/latest) package. To produce a coverage report in the terminal after the tests complete, simply
run pytest as you normally would, with the following added to the end:
`--cov=h2integrate`..

Additional helpful options are `--cov-report=html --no-cov-on-fail` will produce a detailed HTML
report in `htmlcov/` that can be viewed in the browser (open
`/path/to/H2INTEGRATE/htmlcov/index.html`) and skip the coverage report if a test fails.
More options exist, or the highlighted ones can be modified, for example to create a coverage report
for a specific folder or file (e.g., `--cov=h2integrate/core/utilities`), which is especially
helpful when developing tests for a new module.

## Using temporary directories to avoid saving output data

For tests that utilize caching (similar to the HOPP) or non-openmdao ouputs (i.e., plots, data, etc.),
the `temp_dir` fixture should be utilized for 2 reasons.

1. The `temp_dir` fixture successfully removes the temporarily created files after running a module,
   including if a test fails.
2. It avoids locally saving and manually removing example data or tested output files.

`temp_dir` can be incorporated into anything accepts fixtures (i.e., other fixtures and tests).
In the first example, we pass the `temp_dir` to the driver configuration fixture so that the outputs are not
stored until manually cleaned, and the common setup can be recycled for all applicable tests.

:::{literalinclude} ../../h2integrate/converters/co2/marine/test/conftest.py
:start-at: @pytest.fixture(scope="module")
:end-at: return driver_config
:lineno-match:
:::

In the second example, we pass the fixture to another test to show that we can still access the
output data and work with it.

:::{literalinclude} ../../h2integrate/core/test/test_framework.py
:start-at: def test_unsupported_simulation_parameters
:end-at: load_plant_yaml(plant_config_data_dt)
:lineno-match:
:::

The other feature for working more extensively with examples is the `temp_copy_of_example`
located in `examples/test/test_all_examples.py`. This fixture creates a temporary copy
of the example so that an example can be run as it's included in the examples directory.
The example below demonstrates how to make use of the fixture and still have access to all the
examples outputs during the test.

:::{literalinclude} ../../examples/test/test_all_examples.py
:start-at: @pytest.mark.integration
:end-at: model = H2IntegrateModel
:lineno-match:
:::
