from unittest.mock import MagicMock, call

import pytest

from h2integrate.core.commodity_stream_definitions import (
    multivariable_streams,
    add_multivariable_input,
    is_electricity_producer,
    add_multivariable_output,
)


@pytest.mark.unit
def test_is_electricity_producer(subtests):
    with subtests.test("exact match"):
        assert is_electricity_producer("grid_buy")

    with subtests.test("partial starts-with match"):
        assert is_electricity_producer("grid_buy_1")

    with subtests.test("partial ends-with match fails"):
        assert not is_electricity_producer("wrong_grid_buy")

    with subtests.test("empty string fails"):
        assert not is_electricity_producer("")

    with subtests.test("non-electricity producing tech fails"):
        assert not is_electricity_producer("battery")


@pytest.mark.unit
def test_add_multivariable_output(subtests):
    stream_name = "wellhead_gas_mixture"
    n_timesteps = 8760
    component = MagicMock()

    add_multivariable_output(component, stream_name, n_timesteps)

    stream_def = multivariable_streams[stream_name]

    with subtests.test("called once per variable"):
        assert component.add_output.call_count == len(stream_def)

    with subtests.test("correct variable names and kwargs"):
        expected_calls = [
            call(
                f"{stream_name}:{var_name}_out",
                val=0.0,
                shape=n_timesteps,
                units=var_props.get("units"),
                desc=var_props.get("desc", ""),
            )
            for var_name, var_props in stream_def.items()
        ]
        component.add_output.assert_has_calls(expected_calls, any_order=False)

    with subtests.test("uses stream_name:var_name prefix"):
        called_names = [c.args[0] for c in component.add_output.call_args_list]
        for name in called_names:
            assert name.startswith(f"{stream_name}:")
            assert name.endswith("_out")

    with subtests.test("all variables are unique"):
        called_names = [c.args[0] for c in component.add_output.call_args_list]
        assert len(called_names) == len(set(called_names))


@pytest.mark.unit
def test_add_multivariable_input(subtests):
    stream_name = "wellhead_gas_mixture"
    n_timesteps = 8760
    component = MagicMock()

    add_multivariable_input(component, stream_name, n_timesteps)

    stream_def = multivariable_streams[stream_name]

    with subtests.test("called once per variable"):
        assert component.add_input.call_count == len(stream_def)

    with subtests.test("correct variable names and kwargs"):
        expected_calls = [
            call(
                f"{stream_name}:{var_name}_in",
                val=0.0,
                shape=n_timesteps,
                units=var_props.get("units"),
                desc=var_props.get("desc", ""),
            )
            for var_name, var_props in stream_def.items()
        ]
        component.add_input.assert_has_calls(expected_calls, any_order=False)

    with subtests.test("uses stream_name:var_name prefix"):
        called_names = [c.args[0] for c in component.add_input.call_args_list]
        for name in called_names:
            assert name.startswith(f"{stream_name}:")
            assert name.endswith("_in")

    with subtests.test("all variables are unique"):
        called_names = [c.args[0] for c in component.add_input.call_args_list]
        assert len(called_names) == len(set(called_names))


@pytest.mark.unit
def test_add_multivariable_invalid_stream():
    component = MagicMock()
    with pytest.raises(KeyError):
        add_multivariable_output(component, "nonexistent_stream", 10)
    with pytest.raises(KeyError):
        add_multivariable_input(component, "nonexistent_stream", 10)
