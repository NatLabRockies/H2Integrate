"""
Commodity stream definitions for H2Integrate.

This module contains:
1. multivariable_streams: Definitions for streams that bundle multiple related variables
2. is_electricity_producer: Helper function to identify electricity-producing technologies
"""

multivariable_streams = {
    "wellhead_gas": {
        "gas_flow": {
            "units": "kg/h",
            "desc": "Total mass flow rate of gas in the stream",
        },
        "hydrogen_fraction": {
            "units": "unitless",
            "desc": "Fraction of hydrogen in the gas stream",
        },
        "oxygen_fraction": {
            "units": "unitless",
            "desc": "Fraction of oxygen in the gas stream",
        },
        "gas_temperature": {
            "units": "K",
            "desc": "Temperature of the gas stream",
        },
        "gas_pressure": {
            "units": "bar",
            "desc": "Pressure of the gas stream",
        },
    },
    "electricity_ac": {
        "ac_power": {
            "units": "kW",
            "desc": "AC power of the electricity stream",
        },
        "voltage": {
            "units": "V",
            "desc": "Voltage of the electricity stream",
        },
        "frequency": {
            "units": "Hz",
            "desc": "Frequency of the electricity stream",
        },
    },
}


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
        "river",
        "hopp",
        "natural_gas_plant",
        "grid_buy",
    ]

    return any(tech_name.startswith(elem) for elem in electricity_producing_techs)
