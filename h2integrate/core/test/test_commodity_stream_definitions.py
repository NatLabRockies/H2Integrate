from unittest.mock import MagicMock, call

import pytest

from h2integrate.core.commodity_stream_definitions import (
    multivariable_streams,
    add_multivariable_input,
    add_multivariable_output,
)


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


@pytest.mark.unit
def test_add_process_gas_mixture_output(subtests):
    stream_name = "process_gas_mixture"
    n_timesteps = 8760
    component = MagicMock()

    add_multivariable_output(component, stream_name, n_timesteps)

    stream_def = multivariable_streams[stream_name]

    with subtests.test("called once per variable"):
        assert component.add_output.call_count == len(stream_def)

    with subtests.test("correct variable names"):
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

    with subtests.test("has expected variables"):
        called_names = [c.args[0] for c in component.add_output.call_args_list]
        expected_vars = [
            "process_gas_mixture:mass_flow_out",
            "process_gas_mixture:hydrogen_mass_fraction_out",
            "process_gas_mixture:nitrogen_mass_fraction_out",
            "process_gas_mixture:argon_mass_fraction_out",
            "process_gas_mixture:ammonia_mass_fraction_out",
            "process_gas_mixture:temperature_out",
            "process_gas_mixture:pressure_out",
        ]
        assert called_names == expected_vars


@pytest.mark.unit
def test_add_process_gas_mixture_input(subtests):
    stream_name = "process_gas_mixture"
    n_timesteps = 8760
    component = MagicMock()

    add_multivariable_input(component, stream_name, n_timesteps)

    stream_def = multivariable_streams[stream_name]

    with subtests.test("called once per variable"):
        assert component.add_input.call_count == len(stream_def)

    with subtests.test("has expected variables"):
        called_names = [c.args[0] for c in component.add_input.call_args_list]
        expected_vars = [
            "process_gas_mixture:mass_flow_in",
            "process_gas_mixture:hydrogen_mass_fraction_in",
            "process_gas_mixture:nitrogen_mass_fraction_in",
            "process_gas_mixture:argon_mass_fraction_in",
            "process_gas_mixture:ammonia_mass_fraction_in",
            "process_gas_mixture:temperature_in",
            "process_gas_mixture:pressure_in",
        ]
        assert called_names == expected_vars
