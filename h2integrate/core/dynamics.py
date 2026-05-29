"""Reusable primitives for applying dynamic operating constraints to a per-timestep
production profile.

These functions are intentionally model-agnostic: they take and return plain numpy
arrays and a ``dt_seconds`` scalar, with no dependency on OpenMDAO, attrs configs, or
any specific commodity. They are used by ``AmmoniaSynLoopPerformanceModel`` today and
are designed so that other performance models (electrolyzers, methanol
synthesis, etc.) can adopt the same constraints by calling them directly.

The three constraint families exposed are:

- :func:`apply_ramping_limits`: per-timestep upper bound on the change in production
  between consecutive timesteps, expressed as an hourly rate that is scaled to the
  simulation timestep length.
- :func:`find_off_blocks`: low-level helper that returns the start/end indices of
  contiguous "off" segments in a production profile.
- :func:`startup_loss_multiplier`: per-timestep production multiplier representing
  the loss incurred when a plant must restart after being off for a configurable
  minimum off-time. Sub-timestep and multi-timestep off-times and start-up delays
  are handled by a single unified algorithm.
"""

from __future__ import annotations

import numpy as np


def find_off_blocks(profile: np.ndarray, min_production: float) -> np.ndarray:
    """Return an ``(N, 2)`` array of off-block index pairs ``(start, end_exclusive)``.

    A timestep is considered "off" when ``profile[i] < min_production``. Each row
    of the returned array describes a maximal run of consecutive off-timesteps:
    ``profile[start:end_exclusive]`` is fully off, and the timesteps immediately
    before and after the block (when they exist) are on.

    Args:
        profile: 1-D production profile.
        min_production: threshold below which a timestep is considered off.

    Returns:
        Integer array of shape ``(n_blocks, 2)``. May have ``n_blocks == 0``.
    """
    is_off = profile < min_production
    # ``np.r_[0, is_off, 0]`` pads with on-states so edges are detected at array
    # boundaries; ``ediff1d`` then yields +1 at the start of every off-block and
    # -1 at the index immediately after the block ends.
    edges = np.ediff1d(np.r_[0, is_off.astype(int), 0]).nonzero()[0]
    return edges.reshape(-1, 2)


def apply_ramping_limits(
    profile: np.ndarray,
    dt_seconds: float,
    max_ramp_up_per_hr: float,
    max_ramp_down_per_hr: float,
    min_production: float,
    max_production: float,
) -> np.ndarray:
    """Clip each step in ``profile`` to a maximum per-timestep ramp rate.

    The first timestep is taken from ``profile`` unchanged. Each subsequent
    timestep ``i`` is constrained so that
    ``out[i] - out[i-1]`` lies within ``[-max_ramp_down_per_hr * dt_hours,
    +max_ramp_up_per_hr * dt_hours]``. When the requested change exceeds the
    allowed ramp, the new value is set to ``out[i-1] ± max_ramp_per_step`` and
    additionally clipped to ``[min_production, max_production]``. When the
    requested change is within bounds the input value is taken through unchanged
    (no min/max clipping is applied to in-bounds steps, matching the prior
    ammonia-synloop semantics).

    Args:
        profile: 1-D requested production profile.
        dt_seconds: simulation timestep length in seconds.
        max_ramp_up_per_hr: maximum upward ramp rate in production-units / hour.
        max_ramp_down_per_hr: maximum downward ramp rate in production-units / hour.
        min_production: lower bound applied when a step is ramp-limited.
        max_production: upper bound applied when a step is ramp-limited.

    Returns:
        Ramp-limited production profile of the same shape as ``profile``.
    """
    dt_hours = dt_seconds / 3600.0
    max_up_per_step = max_ramp_up_per_hr * dt_hours
    max_down_per_step = max_ramp_down_per_hr * dt_hours

    out = np.empty_like(profile, dtype=float)
    out[0] = profile[0]
    for i in range(1, len(profile)):
        delta = profile[i] - out[i - 1]
        if delta > max_up_per_step:
            out[i] = np.clip(out[i - 1] + max_up_per_step, min_production, max_production)
        elif delta < -max_down_per_step:
            out[i] = np.clip(out[i - 1] - max_down_per_step, min_production, max_production)
        else:
            out[i] = profile[i]
    return out


def _on_block_length(is_off: np.ndarray, start_idx: int) -> int:
    """Length of the contiguous on-block that begins at ``start_idx``.

    Returns 0 when ``start_idx`` is out of range or already an off-step.
    """
    n = len(is_off)
    if start_idx >= n or is_off[start_idx]:
        return 0
    end = start_idx + 1
    while end < n and not is_off[end]:
        end += 1
    return end - start_idx


def startup_loss_multiplier(
    profile: np.ndarray,
    dt_seconds: float,
    offtime_hours: float,
    delay_hours: float,
    min_production: float,
) -> np.ndarray:
    """Per-timestep production multiplier representing start-up losses.

    The algorithm is unified across sub-timestep and multi-timestep off-times and
    start-up delays:

    1. ``offtime_steps = max(ceil(offtime_hours / dt_hours), 1)``. An off-block of
       at least this many consecutive off-timesteps qualifies as a start-up event.
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
        profile: 1-D production profile to analyze (typically post-ramping, pre-startup).
        dt_seconds: simulation timestep length in seconds.
        offtime_hours: minimum continuous off-time (in hours) that triggers a start-up.
        delay_hours: duration of the start-up delay in hours.
        min_production: threshold below which a timestep is considered off.

    Returns:
        Per-timestep multiplier array in ``[0, 1]`` of the same shape as ``profile``.
    """
    n = len(profile)
    multiplier = np.ones(n)

    if delay_hours <= 0:
        # No delay configured; only force off-steps to zero.
        is_off = profile < min_production
        multiplier[is_off] = 0.0
        return multiplier

    dt_hours = dt_seconds / 3600.0
    offtime_steps = max(int(np.ceil(offtime_hours / dt_hours)), 1)

    delay_steps = delay_hours / dt_hours
    full_delay_steps = int(np.floor(delay_steps))
    partial_delay = delay_steps - full_delay_steps
    has_partial = partial_delay > 0
    total_delay_steps = full_delay_steps + (1 if has_partial else 0)

    is_off = profile < min_production
    multiplier[is_off] = 0.0

    off_blocks = find_off_blocks(profile, min_production)
    if off_blocks.size == 0:
        return multiplier

    block_lengths = off_blocks[:, 1] - off_blocks[:, 0]
    qualifying = off_blocks[block_lengths >= offtime_steps]

    for off_end in qualifying[:, 1]:
        if off_end >= n:
            # Off-block extends through the end of the simulation; no on-step exists.
            continue
        on_len = _on_block_length(is_off, int(off_end))
        if on_len >= total_delay_steps:
            # Delay completes within the on-block.
            multiplier[off_end : off_end + full_delay_steps] = 0.0
            if has_partial:
                multiplier[off_end + full_delay_steps] = 1.0 - partial_delay
        else:
            # Start-up was interrupted by the next shut-off; zero the entire on-block.
            # (A more sophisticated model could carry residual delay forward to the
            # next start-up event; for now we conservatively forfeit the on-block.)
            multiplier[off_end : off_end + on_len] = 0.0

    return multiplier
