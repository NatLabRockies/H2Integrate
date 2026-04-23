"""
Commodity stream definitions for H2Integrate.

This module contains:
1. multivariable_streams: Definitions for streams that bundle multiple related variables
2. add_multivariable_output / add_multivariable_input: Helpers to register all
   constituent variables of a multivariable stream on an OpenMDAO component
3. is_electricity_producer: Helper function to identify electricity-producing technologies
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
    # Future multivariable stream definitions can be added here
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


def is_electricity_producer(tech_name: str) -> bool:
    """Check if a technology is an electricity producer.

    Args:
        tech_name: The name of the technology to check.
    Returns:
        True if tech_name starts with any of the known electricity producing
        tech prefixes (e.g., 'wind', 'solar', 'pv', 'grid_buy', etc.).
    Note:
        This uses prefix matching, so 'grid_buy_1' and 'grid_buy_2' would both
        be considered electricity producers. Be careful when naming technologies
        to avoid unintended matches (e.g., 'pv_battery' would be incorrectly
        identified as an electricity producer).
    """

    # add any new electricity producing technologies to this list
    electricity_producing_techs = [
        "wind",
        "solar",
        "pv",
        "tidal",
        "river",
        "hopp",
        "natural_gas_plant",
        "grid_buy",
        "h2_fuel_cell",
        "nuclear",
    ]

    return any(tech_name.startswith(elem) for elem in electricity_producing_techs)
