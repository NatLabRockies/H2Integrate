"""Pure purchase-price and marginal-cost helpers for system-level control."""

import numpy as np
from numpy.typing import ArrayLike


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


def buy_price_profile(buy_price: ArrayLike, n_timesteps: int, plant_life: int) -> np.ndarray:
    """Expand a purchase price to a per-timestep profile without changing the input.

    Per-timestep values take precedence when timestep and plant-life lengths match.
    Otherwise an annual price array uses its first year as the representative price.

    Args:
        buy_price: Scalar, per-timestep, or per-year purchase prices.
        n_timesteps: Number of simulation timesteps.
        plant_life: Plant life in years.

    Returns:
        An independent price array with one value per timestep.
    """
    prices = np.asarray(buy_price)
    if prices.shape == (n_timesteps,) or prices.shape == (1,):
        return np.broadcast_to(prices, n_timesteps).copy()
    if prices.shape == (plant_life,):
        return np.full(n_timesteps, prices[0])
    return np.broadcast_to(prices, n_timesteps).copy()


def annualized_marginal_cost(
    annual_cost: float,
    production: ArrayLike,
    dt_hours: float,
    fraction_of_year_simulated: float,
) -> float:
    """Divide annual operating cost by annualized production.

    Args:
        annual_cost: First-year variable operating cost, including any feedstocks.
        production: Per-timestep production rates.
        dt_hours: Duration of one timestep in hours.
        fraction_of_year_simulated: Simulated duration divided by 8760 hours.

    Returns:
        Cost per produced amount, or zero for nonpositive total production.
    """
    total_production = np.asarray(production).sum() * dt_hours
    if total_production > 0:
        annual_production = total_production / fraction_of_year_simulated
        return annual_cost / annual_production
    return 0.0
