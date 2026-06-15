"""Reusable functions for applying dynamic operating constraints to a per-timestep
production profile.

These functions are intentionally model-agnostic: they take and return plain numpy
arrays and a ``dt_seconds`` scalar, with no dependency on OpenMDAO, attrs configs, or
any specific commodity. They are currently used by ``AmmoniaSynLoopPerformanceModel`` and
are designed so that other performance models (electrolyzers, methanol
synthesis, etc.) can adopt the same constraints by calling them directly.

The two constraint families exposed are:

- :func:`apply_ramping_limits`: per-timestep upper bound on the change in production
  between consecutive timesteps, expressed as an hourly rate that is scaled to the
  simulation timestep length.
- :func:`startup_loss_multiplier`: per-timestep production multiplier representing
  the loss incurred when a plant must restart after being off for some
  minimum off-time. Sub-timestep and multi-timestep off-times and start-up delays
  are handled by a single unified algorithm.
"""

from __future__ import annotations

import math

import numpy as np
from openmdao.utils import units


def find_off_blocks(profile: np.ndarray, min_production: float) -> np.ndarray:
    """Return an ``(N, 2)`` array of off-block index pairs ``(start, end_exclusive)``.

    This is a helper-function for the ``startup_loss_multiplier()`` function.

    A timestep is considered "off" when ``profile[i] < min_production``. Each row
    of the returned array describes a maximal run of consecutive off-timesteps:
    ``profile[start:end_exclusive]`` is fully off, and the timesteps immediately
    before and after the block (when they exist) are on. ``profile`` and
    ``min_production`` must be in the same units (such as `kg/h` or `kg/dt` or `kW`).

    Args:
        profile (np.ndarray): 1-D timeseries production profile.
        min_production (float): threshold below which a timestep is considered off.
            Must be in the same units as ``profile``.

    Returns:
        np.ndarray: Integer array of shape ``(n_blocks, 2)``. May have ``n_blocks == 0``.
    """
    on_off_status = np.where(profile < min_production, 0, 1)
    # ``np.r_[0, is_off, 0]`` pads with on-states so edges are detected at array
    # boundaries; ``ediff1d`` then yields +1 at the start of every off-block and
    # -1 at the index immediately after the block ends.
    edges = np.ediff1d(np.r_[0, on_off_status == 0, 0]).nonzero()[0]
    return edges.reshape(-1, 2)


def check_ramping_at_t0(
    profile,
    max_down_per_step,
):
    """Check that ramp-down constraints are applied at the start of the production profile.

    This method is used in cases where the ``profile`` at t=0 has to be modified so
    that ramping constraint violations don't occur at the start of the simulation.
    This is a helper-function to ``apply_ramping_limits``. This is primarily used
    in the case were a ramp-down event at the start of the production profile that
    violates ramping constraints requires that the starting point (``profile[0]``)
    be reduced.

    Args:
        profile (np.ndarray): 1-D production profile timeseries in amount_units / timestep.
        max_down_per_step (float | int): maximum downward ramp rate in amount units / timestep

    Returns:
        2-element tuple containing

        - **out0** (float | np.ndarray): production profile with applied ramp-down
            constraints at indices of ``i0``
        - **i0** (int | slice): indices of production profile that were already modified
    """
    diff = np.diff(profile)

    # if not ramping down at t=0, no special handling required
    if diff[0] > 0:
        return profile[0], 0

    # get the indices where we're consistently ramping down
    ramp_down_indices = np.flatnonzero(diff < 0)
    if ramp_down_indices.size == 0:
        return profile[0], 0

    first_ramp_down_event_end = np.ediff1d(np.r_[0, diff < 0, 0]).nonzero()[0].reshape(-1, 2)[0][-1]

    # if we're not ramping down faster than the max down per step, no special handling required
    if not np.any(diff[:first_ramp_down_event_end] < max_down_per_step):
        return profile[0], 0

    # flip the profile to go backward
    ramp_down_out = np.zeros(first_ramp_down_event_end + 1)
    ramp_down_profile_reversed = np.flip(profile)[-(first_ramp_down_event_end + 1) :]
    ramp_down_out[0] = ramp_down_profile_reversed[0]
    for i in range(1, len(ramp_down_out), 1):
        delta = np.min([ramp_down_profile_reversed[i] - ramp_down_out[i - 1], max_down_per_step])
        ramp_down_out[i] = ramp_down_out[i - 1] + delta

    return np.flip(ramp_down_out)[:-1], slice(0, int(first_ramp_down_event_end), 1)


def apply_ramping_limits(
    profile_rate: np.ndarray,
    dt_seconds: float,
    max_ramp_up_rate: float,
    max_ramp_down_rate: float,
    commodity_rate_units: str,
    commodity_amount_units: str | None,
) -> np.ndarray:
    """Clip each step in ``profile`` to a maximum per-timestep ramp rate.

    Each timestep ``i`` is constrained so that
    ``out[i] - out[i-1]`` lies within ``[-max_ramp_down_rate,
    +max_ramp_up_rate]``. When the requested change exceeds the
    allowed ramp, the new value is set to ``out[i-1] ± max_ramp_per_step`` and
    additionally clipped to ``[min_production, max_production]``. When the
    requested change is within bounds the input value is taken through unchanged
    (no min/max clipping is applied to in-bounds steps, matching the prior
    ammonia-synloop semantics).

    Args:
        profile_rate (np.ndarray): commodity profile in units of ``commodity_rate_units``
        dt_seconds (int): simulation timestep length in seconds.
        max_ramp_up_rate (float | int): maximum upward ramp rate in ``commodity_rate_units``
        max_ramp_down_rate (float | int): maximum downward ramp rate in ``commodity_rate_units``
        commodity_rate_units (str): the rate units of the ``profile_rate`` (such as kW or kg/h)
        commodity_amount_units (str): the corresponding amount units of the commodity
            (such as kW*h or kg)
    Returns:
        np.ndarray: Ramp-limited production profile of the same shape as ``profile_rate``
            in ``commodity_rate_units``
    """
    if commodity_amount_units is None:
        commodity_amount_units = f"({commodity_rate_units})*h"

    # convert the input rates to be on a per-timestep basis
    max_down_per_step = units.convert_units(
        max_ramp_down_rate, commodity_rate_units, f"({commodity_amount_units})/({dt_seconds}*s)"
    )
    max_up_per_step = units.convert_units(
        max_ramp_up_rate, commodity_rate_units, f"({commodity_amount_units})/({dt_seconds}*s)"
    )
    profile = units.convert_units(
        profile_rate, commodity_rate_units, f"({commodity_amount_units})/({dt_seconds}*s)"
    )

    out0, i0 = check_ramping_at_t0(profile, max_down_per_step)

    out = np.zeros_like(profile, dtype=float)
    out[i0] = out0
    i_start = i0.stop + 1 if isinstance(i0, slice) else i0 + 1

    for i in range(i_start, len(profile)):
        # get the change over time of the actual production and
        # constrained production
        delta = profile[i] - out[i - 1]

        # Ramping-up: apply ramp-up constraint
        if delta > max_up_per_step:
            out[i] = np.clip(out[i - 1] + max_up_per_step, 0.0, profile[i])

        # Ramping-down: apply ramp-down constraint
        elif delta < -max_down_per_step:
            # number of timesteps to go back and adjust so ramp-down never exceeds actual production
            timeback = math.ceil(delta / -max_down_per_step)
            # need to start adjustment at timeback steps back, and adjust forward until i.
            if timeback <= 1:
                out[i] = np.clip(out[i - 1] - max_down_per_step, 0.0, profile[i])
            else:
                # If timeback > 1, we need to adjust the previous timeback steps to
                # ensure we don't exceed the max ramp down rate.
                for j in range(max([1, i - timeback]), i):
                    # Determine that max and minimum production at j
                    max_out_at_j = np.clip(out[j - 1] + max_up_per_step, 0.0, profile[j])
                    min_out_at_j = np.clip(out[j - 1] - max_down_per_step, 0.0, profile[j])
                    n_dt_left = i - j
                    # See if we can ramp-up more between times j and i
                    if ((max_out_at_j - profile[i]) / max_down_per_step) > n_dt_left:
                        # should not increase, would take too long to decrease
                        out[j] = min_out_at_j
                    else:
                        # should increase, can decrease in following timesteps
                        out[j] = max_out_at_j
        # No constraint on ramping
        else:
            out[i] = np.max([profile[i], 0.0])

    # convert units back to rate units
    out_rate = units.convert_units(
        out,
        f"({commodity_amount_units})/({dt_seconds}*s)",
        commodity_rate_units,
    )
    return out_rate


def _on_block_length(is_on: np.ndarray, start_idx: int) -> int:
    """Length of the contiguous on-block that begins at ``start_idx``.

    Returns 0 when ``start_idx`` is out of range or already an off-step.

    Args:
        is_on (np.ndarray): array with values of 0.0 when "off", and greater
            than 0.0 when "on"
        start_idx (int): index of ``is_on`` to search for length of "on" block

    Returns:
        int: number of consecutive on-hours starting at ``start_idx``
    """
    n = len(is_on)
    if start_idx >= n or not bool(is_on[start_idx]):
        return 0

    # Get edges where the its on after start_idx
    onindx, offindx = (
        np.ediff1d(np.r_[0, is_on[start_idx:] > 0.0, 0]).nonzero()[0].reshape(-1, 2)[0]
    )

    return int(offindx - onindx)


def startup_loss_multiplier(
    profile: np.ndarray,
    dt_seconds: float,
    offtime_hours: float,
    delay_hours: float,
    min_production: float,
    max_offtime_hours: float | None = None,
) -> np.ndarray:
    """Per-timestep production multiplier representing start-up losses.

    The algorithm is unified across sub-timestep and multi-timestep off-times and
    start-up delays:

    1. ``offtime_steps = max(ceil(offtime_hours / dt_hours), 1)``. An off-block of
       at least this many consecutive off-timesteps qualifies as a start-up event.
       When ``max_offtime_hours`` is provided, off-blocks at or above
       ``ceil(max_offtime_hours / dt_hours)`` consecutive off-timesteps are
       *excluded* -- this lets a caller chain two passes (e.g. warm + cold) so
       that each off-block triggers at most one start-up event.
    2. The start-up delay is decomposed into ``full_delay_steps`` whole timesteps
       of zero production and an optional trailing partial timestep with multiplier
       ``1 - partial_delay``.
    3. For each qualifying off-block, the following on-block receives the full delay
       schedule. If the on-block is shorter than the total delay (``full_delay_steps
       + 1`` if there is a partial component, else ``full_delay_steps``), the entire
       on-block is zeroed to represent an interrupted start-up.
    4. Every off-timestep gets multiplier 0.

    The multiplier is derived purely from the on/off pattern of ``profile``, so the
    same reference profile can be passed to multiple successive start-up passes
    (for example warm + cold) and their multipliers can be combined by element-wise
    multiplication without one pass's zeros being misread as new off-events.

    Args:
        profile (np.ndarray): 1-D production profile to analyze
            (typically post-ramping, pre-startup).
        dt_seconds (int): simulation timestep length in seconds.
        offtime_hours (int | float): minimum continuous off-time (in hours) that triggers a
            start-up event.
        delay_hours (int | float): duration of the start-up delay in hours.
        min_production (int | float): threshold below which a timestep is considered off.
        max_offtime_hours (int | float | None): optional upper bound on off-block length, in hours.
            Off-blocks at or above this length are *excluded* from the multiplier (left at 1.0 on
            the following on-block). Off-steps within those blocks are still zeroed. Use this
            to make a "warm-start" pass ignore off-blocks that should be classified as
            cold-start events instead. ``None`` (the default) imposes no upper bound.

    Returns:
        np.ndarray: Per-timestep multiplier array in ``[0, 1]`` of the same shape as ``profile``.
    """
    # set the multiplier to 1 when profile>min_production
    multiplier = np.where(profile < min_production, 0.0, 1.0)

    if delay_hours <= 0:
        # No delay configured; only force off-steps to zero.
        return multiplier

    # Convert off-time and delay into units of the timestep
    delay_steps = delay_hours * 3600 / dt_seconds
    offtime_steps = max(int(np.ceil(offtime_hours * 3600 / dt_seconds)), 1)
    full_delay_steps = int(delay_steps // 1)  # number of full timesteps in start-up delay
    partial_delay = delay_steps % 1  # fraction of timestep in start-up delay
    total_delay_steps = full_delay_steps + (1 if partial_delay > 0 else 0)

    off_blocks = find_off_blocks(profile, min_production)
    if off_blocks.size == 0:
        return multiplier

    # list of the duration of off-periods
    block_lengths = off_blocks[:, 1] - off_blocks[:, 0]

    # True when off-time triggers a start-up event
    qualifying_mask = block_lengths >= offtime_steps
    if max_offtime_hours is not None:
        # Exclude blocks that are long enough to be handled by a different (more
        # severe) start-up pass. ``ceil`` matches the threshold convention used
        # for ``offtime_steps`` so the two passes partition off-blocks cleanly.
        max_offtime_steps = max(int(np.ceil(max_offtime_hours * 3600 / dt_seconds)), 1)
        qualifying_mask &= block_lengths < max_offtime_steps
    qualifying = off_blocks[qualifying_mask]

    for off_end in qualifying[:, 1]:
        if off_end >= len(profile):
            # Off-block extends through the end of the simulation; no on-step exists.
            continue
        on_len = _on_block_length(multiplier, int(off_end))
        if on_len >= total_delay_steps:
            # Delay completes within the on-block.
            multiplier[off_end : off_end + full_delay_steps] = 0.0
            if partial_delay > 0.0:
                multiplier[off_end + full_delay_steps] = 1.0 - partial_delay
        else:
            # Start-up was interrupted by the next shut-off; zero the entire on-block.
            # (A more sophisticated model could carry residual delay forward to the
            # next start-up event; for now we conservatively forfeit the on-block.)
            multiplier[off_end : off_end + on_len] = 0.0

    return multiplier.astype(float)
