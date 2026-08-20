"""
Commodity stream definitions for H2Integrate.

This module contains:

1. multivariable_streams: Definitions for streams that bundle multiple related variables
2. add_multivariable_output / add_multivariable_input: Helpers to register all
   constituent variables of a multivariable stream on an OpenMDAO component
"""

multivariable_streams = {
    "wellhead_gas_mixture": {
        "mass_flow": {
            "units": "kg/h",
            "desc": "Total mass flow rate of gas in the stream",
        },
        "hydrogen_mass_fraction": {
            "units": "unitless",
            "desc": "Mass fraction of hydrogen in the gas stream",
        },
        "oxygen_mass_fraction": {
            "units": "unitless",
            "desc": "Mass fraction of oxygen in the gas stream",
        },
        "temperature": {
            "units": "K",
            "desc": "Temperature of the gas stream",
        },
        "pressure": {
            "units": "bar",
            "desc": "Pressure of the gas stream",
        },
    },
    "process_gas_mixture": {
        "mass_flow": {
            "units": "kg/h",
            "desc": "Total gas mass flow rate",
        },
        "hydrogen_mass_fraction": {
            "units": "unitless",
            "desc": "Mass fraction of hydrogen in the gas stream",
        },
        "nitrogen_mass_fraction": {
            "units": "unitless",
            "desc": "Mass fraction of nitrogen in the gas stream",
        },
        "argon_mass_fraction": {
            "units": "unitless",
            "desc": "Mass fraction of argon in the gas stream",
        },
        "ammonia_mass_fraction": {
            "units": "unitless",
            "desc": "Mass fraction of ammonia in the gas stream",
        },
        "temperature": {
            "units": "K",
            "desc": "Gas stream temperature",
        },
        "pressure": {
            "units": "bar",
            "desc": "Gas stream pressure",
        },
    },
}


def add_multivariable_output(component, stream_name: str, n_timesteps: int) -> None:
    """Add all constituent variables of a multivariable stream as outputs.

    For each variable defined in ``multivariable_streams[stream_name]``, an
    output named ``<stream_name>:<var_name>_out`` is added to *component*.

    Args:
        component: An OpenMDAO component instance (must have ``add_output``).
        stream_name: Key into :data:`multivariable_streams`.
        n_timesteps: Length of the time-series dimension.

    Raises:
        KeyError: If *stream_name* is not in :data:`multivariable_streams`.
    """
    for var_name, var_props in multivariable_streams[stream_name].items():
        component.add_output(
            f"{stream_name}:{var_name}_out",
            val=0.0,
            shape=n_timesteps,
            units=var_props.get("units"),
            desc=var_props.get("desc", ""),
        )


def add_multivariable_input(component, stream_name: str, n_timesteps: int) -> None:
    """Add all constituent variables of a multivariable stream as inputs.

    For each variable defined in ``multivariable_streams[stream_name]``, an
    input named ``<stream_name>:<var_name>_in`` is added to *component*.

    Args:
        component: An OpenMDAO component instance (must have ``add_input``).
        stream_name: Key into :data:`multivariable_streams`.
        n_timesteps: Length of the time-series dimension.

    Raises:
        KeyError: If *stream_name* is not in :data:`multivariable_streams`.
    """
    for var_name, var_props in multivariable_streams[stream_name].items():
        component.add_input(
            f"{stream_name}:{var_name}_in",
            val=0.0,
            shape=n_timesteps,
            units=var_props.get("units"),
            desc=var_props.get("desc", ""),
        )
