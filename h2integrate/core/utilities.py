from typing import Any
from collections import OrderedDict

import attrs
import numpy as np
import pandas as pd
from attrs import Attribute, define


try:
    from pyxdsm.XDSM import FUNC, XDSM
except ImportError:
    pass


def create_xdsm_from_config(config, output_file="connections_xdsm"):
    """
    Create an XDSM diagram from a given plant configuration and save it to a pdf file.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing technology interconnections.
    output_file : str, optional
        The name of the output file where the XDSM diagram will be saved.
    """
    # Create an XDSM object
    x = XDSM(use_sfmath=True)

    # Use an OrderedDict to keep the order of technologies
    technologies = OrderedDict()
    if "technology_interconnections" not in config:
        return

    for conn in config["technology_interconnections"]:
        technologies[conn[0]] = None  # Source
        technologies[conn[1]] = None  # Destination

    # Add systems to the XDSM
    for tech in technologies.keys():
        tech_label = tech.replace("_", r"\_")
        x.add_system(tech, FUNC, rf"\text{{{tech_label}}}")

    # Add connections
    for conn in config["technology_interconnections"]:
        if len(conn) == 3:
            source, destination, data = conn
        else:
            source, destination, data, label = conn

        if isinstance(data, list | tuple) and len(data) >= 2:
            data = f"{data[0]} as {data[1]}"

        if len(conn) == 3:
            connection_label = rf"\text{{{data}}}"
        else:
            connection_label = rf"\text{{{data} {'via'} {label}}}"

        connection_label = connection_label.replace("_", r"\_")

        x.connect(source, destination, connection_label)

    # Write the diagram to a file
    x.write(output_file, quiet=True)
    print(f"XDSM diagram written to {output_file}.pdf")


def merge_shared_inputs(config, input_type):
    """
    Merges two dictionaries from a configuration object and resolves potential conflicts.

    This function combines the dictionaries associated with `shared_parameters` and
    `performance_parameters`, `cost_parameters`, or `finance_parameters` in the provided
    `config` dictionary. If both dictionaries contain the same keys,
    a ValueError is raised to prevent duplicate parameter definitions.

    Parameters:
        config (dict): A dictionary containing configuration data. It must include keys
                       like `shared_parameters` and `{input_type}_parameters`.
        input_type (str): The type of input parameters to merge. Valid values are
                          'performance', 'control', 'cost', or 'finance'.

    Returns:
        dict: A merged dictionary containing parameters from both `shared_parameters`
              and `{input_type}_parameters`. If one of the dictionaries is missing,
              the function returns the existing dictionary.

    Raises:
        ValueError: If duplicate keys are found in `shared_parameters` and
                    `{input_type}_parameters`.
    """

    if f"{input_type}_parameters" in config.keys() and "shared_parameters" in config.keys():
        common_keys = config[f"{input_type}_parameters"].keys() & config["shared_parameters"].keys()
        if common_keys:
            raise ValueError(
                f"Duplicate parameters found: {', '.join(common_keys)}. "
                f"Please define parameters only once in the shared and {input_type} dictionaries."
            )
        return {**config[f"{input_type}_parameters"], **config["shared_parameters"]}
    elif "shared_parameters" not in config.keys():
        return config[f"{input_type}_parameters"]
    else:
        return config["shared_parameters"]


@define(kw_only=True)
class BaseConfig:
    """
    A Mixin class to allow for kwargs overloading when a data class doesn't
    have a specific parameter defined. This allows passing of larger dictionaries
    to a data class without throwing an error.
    """

    @classmethod
    def from_dict(cls, data: dict, strict=True, additional_cls_name: str | None = None):
        """Maps a data dictionary to an ``attrs``-defined class.

        Args:
            data (dict): The data dictionary to be mapped.
            strict (bool): A flag enabling strict parameter processing, meaning that no extra
                parameters may be passed in or an AttributeError will be raised.
            additional_cls_name (str | None): The name of the model class creating the configuration
                data class. Provides an easier to diagnose error message for end users when
                the class name is provided.

        Returns:
            cls: The ``attrs``-defined class.
        """
        # Check for any inputs that aren't part of the class definition
        if strict is True:
            class_attr_names = [a.name for a in cls.__attrs_attrs__]
            extra_args = [d for d in data if d not in class_attr_names]
            if len(extra_args):
                if additional_cls_name is not None:
                    msg = (
                        f"{additional_cls_name} setup failed as a result of {cls.__name__}"
                        f" receiving extraneous inputs: {extra_args}"
                    )
                else:
                    msg = (
                        f"The initialization for {cls.__name__} was given extraneous "
                        f"inputs: {extra_args}"
                    )
                raise AttributeError(msg)

        kwargs = {a.name: data[a.name] for a in cls.__attrs_attrs__ if a.name in data and a.init}

        # Map the inputs must be provided: 1) must be initialized, 2) no default value defined
        required_inputs = [
            a.name for a in cls.__attrs_attrs__ if a.init and a.default is attrs.NOTHING
        ]
        undefined = sorted(set(required_inputs) - set(kwargs))

        if undefined:
            if additional_cls_name is not None:
                msg = (
                    f"{additional_cls_name} setup failed as a result of {cls.__name__}"
                    f" missing the following inputs: {undefined}"
                )
            else:
                msg = (
                    f"The class definition for {cls.__name__} is missing the following inputs: "
                    f"{undefined}"
                )
            raise AttributeError(msg)
        return cls(**kwargs)

    def as_dict(self) -> dict:
        """Creates a JSON and YAML friendly dictionary that can be save for future reloading.
        This dictionary will contain only `Python` types that can later be converted to their
        proper `Turbine` formats.

        Returns:
            dict: All key, value pairs required for class re-creation.
        """
        return attrs.asdict(self, filter=attr_filter, value_serializer=attr_serializer)


def attr_serializer(inst: type, field: Attribute, value: Any):
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def attr_filter(inst: Attribute, value: Any) -> bool:
    if inst.init is False:
        return False
    if value is None:
        return False
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return False
    return True


def build_time_series_from_plant_config(plant_config):
    """Build simulation timestamps from the simulation settings in a plant config.

    Extracts ``n_timesteps``, ``dt``, ``timezone``, and ``start_time`` from
    ``plant_config["plant"]["simulation"]`` and delegates to
    :func:`build_time_series`.

    Args:
        plant_config (dict): Plant-level configuration dictionary. Must contain
            a ``plant.simulation`` sub-dict with the following keys:

            - ``n_timesteps`` (int): Number of simulation timesteps.
            - ``dt`` (int): Timestep size in seconds.
            - ``timezone`` (int): UTC offset in integer hours (e.g., ``-6`` for
              UTC-6).
            - ``start_time`` (str): Start timestamp parseable by
              :class:`pandas.Timestamp`.

    Returns:
        numpy.ndarray: Array of :class:`datetime.datetime` objects of length
        ``n_timesteps``, equally spaced by ``dt`` seconds, starting at
        ``start_time`` in the specified timezone.
    """
    simulation_cfg = plant_config["plant"]["simulation"]
    n_timesteps = int(simulation_cfg["n_timesteps"])
    dt_seconds = int(simulation_cfg["dt"])
    tz = int(simulation_cfg["timezone"])
    start_time = simulation_cfg["start_time"]

    return build_time_series(
        start_time=start_time, dt_seconds=dt_seconds, n_timesteps=n_timesteps, time_zone=tz
    )


def build_time_series(
    start_time: str,
    dt_seconds: int,
    n_timesteps: int,
    time_zone: int,
    start_year: int | None = None,
):
    """Build an array of evenly spaced timezone-aware datetime objects.

    Constructs a :class:`pandas.DatetimeIndex` of length ``n_timesteps``
    beginning at ``start_time`` with a fixed frequency of ``dt_seconds``
    seconds, then converts it to a NumPy array of :class:`datetime.datetime`
    objects via :meth:`pandas.DatetimeIndex.to_pydatetime`.

    Args:
        start_time (str): Start timestamp string parseable by
            :class:`pandas.Timestamp` (e.g., ``"2025-01-01 00:00:00"`` or
            ``"01-01 00:00:00"`` when ``start_year`` is provided).
        dt_seconds (int): Timestep duration in seconds (e.g., ``3600`` for
            hourly, ``1800`` for half-hourly).
        n_timesteps (int): Number of timestamps to generate.
        time_zone (int): UTC offset in integer hours applied to the series
            (e.g., ``-6`` for UTC-6).
        start_year (int | None, optional): If provided, overrides the year
            component of ``start_time``. Useful when ``start_time`` omits the
            year. Defaults to ``None``.

    Returns:
        numpy.ndarray: Array of :class:`datetime.datetime` objects of length
        ``n_timesteps``, equally spaced by ``dt_seconds`` seconds.
    """

    start_timestamp = pd.Timestamp(start_time, tz=time_zone, year=start_year)
    freq = pd.to_timedelta(dt_seconds, unit="s")

    return pd.date_range(start=start_timestamp, periods=n_timesteps, freq=freq).to_pydatetime()
