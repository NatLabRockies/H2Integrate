"""Pure purchase-price configuration helpers for system-level control."""

import numpy as np


def _get_tech_buy_price_input_name(tech_config: dict, tech_name: str) -> str | None:
    """Return the variable name of a tech's buy-price input, or ``None`` if absent.

    Used by the ``"buy_price"`` ``cost_per_tech`` mode to figure out which
    OpenMDAO input on the technology cost model carries the per-unit purchase
    price. Currently recognizes:

    - ``"electricity_buy_price"`` (Grid technologies)
    - ``"price"`` (Feedstock technologies)

    Args:
        tech_config (dict): The full ``tech_config`` dictionary.
        tech_name (str): Name of the technology.

    Returns:
        str | None: The input variable name, or ``None`` if the tech has no
        recognized buy-price input in its cost / shared parameters.
    """
    model_inputs = tech_config.get("technologies", {}).get(tech_name, {}).get("model_inputs", {})
    parameters = {
        **model_inputs.get("shared_parameters", {}),
        **model_inputs.get("cost_parameters", {}),
    }
    if "electricity_buy_price" in parameters:
        return "electricity_buy_price"
    if "price" in parameters:
        return "price"
    return None


def _get_buy_price_default_and_shape(
    tech_config: dict, tech_name: str, n_timesteps: int, plant_life: int
) -> tuple[float | list | np.ndarray, int]:
    """Return the default buy-price value and OpenMDAO input shape for a tech.

    Mirrors the shape logic used by the technology cost models themselves so
    the SLC's ``{tech_name}_buy_price`` input can be safely connected
    input-to-input with the tech's own buy-price input:

    - Grid (``electricity_buy_price``): shape is determined by
      ``buy_price_mode`` (``per_timestep`` -> ``n_timesteps``, ``per_year`` ->
      ``plant_life``, ``constant`` -> ``1``).
    - Feedstock (``price``): shape is the length of the configured price
      array, or ``1`` for a scalar.
    - Anything else: falls back to ``n_timesteps`` with a default of ``0.0``.

    Args:
        tech_config (dict): The full ``tech_config`` dictionary.
        tech_name (str): Name of the technology.
        n_timesteps (int): Number of simulation timesteps.
        plant_life (int): Plant life in years.

    Returns:
        tuple[float | list | np.ndarray, int]: ``(default_value, shape)``
        suitable for ``add_input(val=..., shape=...)``.
    """
    model_inputs = tech_config.get("technologies", {}).get(tech_name, {}).get("model_inputs", {})
    parameters = {
        **model_inputs.get("shared_parameters", {}),
        **model_inputs.get("cost_parameters", {}),
    }
    if "electricity_buy_price" in parameters:
        mode = parameters.get("buy_price_mode", "per_timestep")
        shape = plant_life if mode == "per_year" else 1 if mode == "constant" else n_timesteps
        return parameters["electricity_buy_price"], shape
    if "price" in parameters:
        price = parameters["price"]
        return price, len(price) if isinstance(price, list | np.ndarray) else 1
    return 0.0, n_timesteps
