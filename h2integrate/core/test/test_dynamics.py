import numpy as np
import pytest

from h2integrate.core.dynamics import find_off_blocks, apply_ramping_limits, startup_loss_multiplier


@pytest.mark.unit
def test_find_off_blocks(subtests):
    min_prod = 1.0

    with subtests.test("No off-blocks when profile is fully on"):
        profile = np.array([5.0, 5.0, 5.0, 5.0])
        blocks = find_off_blocks(profile, min_prod)
        assert blocks.shape == (0, 2)

    with subtests.test("Single interior off-block"):
        profile = np.array([5.0, 0.0, 0.0, 5.0])
        blocks = find_off_blocks(profile, min_prod)
        assert np.array_equal(blocks, np.array([[1, 3]]))

    with subtests.test("Multiple off-blocks including boundaries"):
        profile = np.array([0.0, 5.0, 0.0, 0.0, 5.0, 0.0])
        blocks = find_off_blocks(profile, min_prod)
        assert np.array_equal(blocks, np.array([[0, 1], [2, 4], [5, 6]]))

    with subtests.test("Threshold is strict less-than (== min_prod is on)"):
        profile = np.array([1.0, 0.5, 1.0])
        blocks = find_off_blocks(profile, min_prod)
        assert np.array_equal(blocks, np.array([[1, 2]]))

    with subtests.test("Profile fully off is a single block spanning the timeseries"):
        profile = np.zeros(4)
        blocks = find_off_blocks(profile, min_prod)
        assert np.array_equal(blocks, np.array([[0, 4]]))

    with subtests.test("On-block of length 1 separates two off-blocks"):
        profile = np.array([0.0, 5.0, 0.0, 0.0, 5.0])
        blocks = find_off_blocks(profile, min_prod)
        assert np.array_equal(blocks, np.array([[0, 1], [2, 4]]))

    with subtests.test("Single-step alternating profile yields one block per off-step"):
        profile = np.array([0.0, 5.0, 0.0, 5.0, 0.0])
        blocks = find_off_blocks(profile, min_prod)
        assert np.array_equal(blocks, np.array([[0, 1], [2, 3], [4, 5]]))


@pytest.mark.unit
def test_apply_ramping_limits(subtests):
    dt = 3600.0  # 1 hour
    rate_up = 2.0
    rate_down = 1.0

    with subtests.test("In-bounds steps pass through unchanged"):
        profile = np.array([0.0, 1.0, 2.0, 1.5])
        out = apply_ramping_limits(
            profile,
            dt,
            rate_up,
            rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, profile)

    with subtests.test("Up-ramp clipped to max rate per step"):
        profile = np.array([0.0, 10.0, 10.0])
        out = apply_ramping_limits(
            profile,
            dt,
            rate_up,
            rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        # Step 1: 0 -> requested 10, capped at +2 -> 2. Step 2: 2 -> requested 10, capped -> 4.
        assert np.allclose(out, [0.0, 2.0, 4.0])

    with subtests.test("Down-ramp clipped to max rate per step and is <= profile"):
        profile = np.array([10.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            rate_up,
            rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )

        assert np.allclose(out, [1.0, 0.0, 0.0])

    with subtests.test("Down-ramp at start clipped to max rate per step and is <= profile"):
        profile = np.array([10.0, 5.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            rate_up,
            rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )

        assert np.allclose(out, [2.0, 1.0, 0.0, 0.0])

    with subtests.test("Per-step delta scales with dt"):
        profile = np.array([0.0, 10.0, 10.0])
        out = apply_ramping_limits(
            profile,
            dt_seconds=1800.0,
            max_ramp_up_rate=rate_up,
            max_ramp_down_rate=rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        # dt_hours = 0.5, max_up_per_step = 1.0 kg/timestep = 2.0 kg/h
        # out is in kg/h
        assert np.allclose(out, [0.0, 2.0, 4.0])

    with subtests.test("Ramp-limited steps are clipped to [min, max]"):
        # Down-ramping toward 0 below min_production=2: steps clipped to min.
        profile = np.array([5.0, 0.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=10.0,
            max_ramp_down_rate=1.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )

        assert np.allclose(out, [1.0, 0.0, 0.0, 0.0])

    with subtests.test("First timestep is taken from input unchanged"):
        profile = np.array([7.5, 7.5])
        out = apply_ramping_limits(
            profile,
            dt,
            rate_up,
            rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert out[0] == 7.5

    with subtests.test("Up-ramp clipped at profile"):
        # In-bounds delta but request exceeds max_production -> clipped to max.
        profile = np.array([5.0, 7.0, 9.0, 11.0])
        out = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=5.0,
            max_ramp_down_rate=5.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, [5.0, 7.0, 9.0, 11.0])

    with subtests.test("Asymmetric rates: slow up, fast down"):
        # max_up=1/hr, max_down=5/hr. Up-ramp from 0 is the binding constraint.
        profile = np.array([0.0, 5.0, 5.0, 0.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=1.0,
            max_ramp_down_rate=5.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, [0.0, 1.0, 2.0, 0.0, 0.0, 0.0])

    with subtests.test("All zeros pass through unchanged"):
        profile = np.zeros(5)
        out = apply_ramping_limits(
            profile,
            dt,
            rate_up,
            rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, np.zeros(5))

    with subtests.test("Sustained max production passes through unchanged"):
        profile = np.full(5, 10.0)
        out = apply_ramping_limits(
            profile,
            dt,
            rate_up,
            rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, np.full(5, 10.0))

    with subtests.test("Down-ramp at the very end of timeseries is rate-limited"):
        # Last timestep requests a steep drop; rate-limit clips it to one step's worth.
        profile = np.array([5.0, 5.0, 5.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            rate_up,
            rate_down,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        # Steady run -> single down-step. Initial value is back-propagated by
        # check_ramping_at_t0 because the leading down-event spans the whole array.
        assert np.allclose(out, [3.0, 2.0, 1.0, 0.0])

    with subtests.test("In-rate monotonic down-ramp passes through unchanged"):
        # |delta|=1 == max_down_per_step exactly; check_ramping_at_t0 does not
        # trigger because no diff is strictly less than max_down_per_step.
        profile = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
        out = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=1.0,
            max_ramp_down_rate=1.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        # The very last in-bounds step is clipped to max_down=1, but here the
        # request is exactly at the rate limit so it falls through and the final
        # step is forced to 0 by the timeback>1 path. Document observed behavior.
        assert np.allclose(out, [5.0, 4.0, 3.0, 2.0, 0.0])

    with subtests.test("Sub-hour dt scales the per-step ramp limit"):
        # dt=900s -> 0.25 h; rate=4/hr -> 1 unit per step.
        profile = np.array([0.0, 16.0, 16.0, 16.0])  # kg/h
        out = apply_ramping_limits(
            profile,
            dt_seconds=900.0,  # 15 min
            max_ramp_up_rate=4.0,  # 4 kg/h, 1 kg/dt
            max_ramp_down_rate=4.0,  # kg/h, 1 kg/dt
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, [0.0, 4.0, 8.0, 12.0])

    with subtests.test("Turndown floor (min_production>0) raises ramp-limited steps to floor"):
        # min_production acts as a hard floor for any step that goes through the
        # ramp-limited or in-bounds clip branch. Documents observed behavior of
        # the timeback>1 retroactive look-back combined with the [min,max] clip.
        profile = np.array([5.0, 0.0, 0.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=1.0,
            max_ramp_down_rate=1.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, [1.0, 0.0, 0.0, 0.0, 0.0])

    with subtests.test("Steep down-ramp triggers retroactive look-back zeroing"):
        # Off-event (rate=1) preceded by a peak (5) larger than n_dt_left can
        # decrease across causes the inner timeback>1 branch to zero out the
        # preceding on-block.
        profile = np.array([0.0, 5.0, 5.0, 0.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=5.0,
            max_ramp_down_rate=1.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, np.zeros(6))

    with subtests.test("In-range up-then-down round-trip leaves shape intact"):
        # Both the up-ramp and down-ramp deltas are within the rate, so the
        # profile passes through (with the in-bounds clip being a no-op).
        profile = np.array([0.0, 6.0, 6.0, 0.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=6.0,
            max_ramp_down_rate=6.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(out, profile)


@pytest.mark.unit
def test_startup_loss_multiplier(subtests):
    dt = 3600.0  # 1 hour timesteps
    min_prod = 1.0
    rated = 10.0

    with subtests.test("delay_hours <= 0 only zeros off-steps"):
        profile = np.array([rated, 0.0, 0.0, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=1.0, delay_hours=0.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 1.0, 1.0])

    with subtests.test("Whole-step delay zeros first delay_steps of following on-block"):
        # off for 3 hrs (>= offtime_hours=2), then on for 4 hrs. Delay = 2 hrs -> 2 zero on-steps.
        profile = np.array([rated, 0.0, 0.0, 0.0, rated, rated, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=2.0, delay_hours=2.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0])

    with subtests.test("Partial-step delay produces fractional multiplier"):
        # Delay = 2.25 hrs -> 2 full zero steps + 1 partial step at multiplier 0.75.
        profile = np.array([rated, 0.0, 0.0, 0.0, rated, rated, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=2.0, delay_hours=2.25, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.75, 1.0])

    with subtests.test("Off-blocks shorter than offtime_steps do not trigger startup"):
        # offtime_hours=2.5 -> offtime_steps = ceil(2.5)=3. A 2-hr off-block is sub-threshold.
        profile = np.array([rated, 0.0, 0.0, rated, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=2.5, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 1.0, 1.0, 1.0])

    with subtests.test("On-block shorter than total delay is fully zeroed"):
        # Off for 3 hrs, on for only 1 hr, then off again. Delay = 2 hrs > on-block length.
        profile = np.array([rated, 0.0, 0.0, 0.0, rated, 0.0, 0.0])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=2.0, delay_hours=2.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    with subtests.test("offtime_hours below dt still requires at least one off-step"):
        # offtime_hours=0.25, dt=1h -> offtime_steps = max(ceil(0.25), 1) = 1. Single off-step
        # qualifies and triggers a 1-hr delay.
        profile = np.array([rated, 0.0, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=0.25, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 1.0])

    with subtests.test("Sub-dt delay yields a single partial step"):
        # delay_hours=0.5, dt=1h -> 0 full steps + 1 partial step at multiplier 0.5.
        profile = np.array([rated, 0.0, 0.0, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=1.0, delay_hours=0.5, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 0.5, 1.0])

    with subtests.test("Multiplier derived from on/off pattern only (passes commute)"):
        # Same profile, two passes; their multipliers should commute under elementwise product.
        profile = np.array([rated, 0.0, 0.0, 0.0, rated, rated, rated, rated])
        m1 = startup_loss_multiplier(
            profile, dt, offtime_hours=2.0, delay_hours=2.0, min_production=min_prod
        )
        m2 = startup_loss_multiplier(
            profile, dt, offtime_hours=1.0, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(m1 * m2, m2 * m1)

    with subtests.test("dt scaling: 1.5-hr delay at dt=1800s = 3 half-hour zero steps"):
        # dt=1800s (0.5 h). delay_hours=1.5 -> delay_steps=3, all full.
        # offtime_hours=1.0 -> offtime_steps=2. Profile: on, off, off, on, on, on, on.
        profile = np.array([rated, 0.0, 0.0, rated, rated, rated, rated])
        mult = startup_loss_multiplier(
            profile,
            dt_seconds=1800.0,
            offtime_hours=1.0,
            delay_hours=1.5,
            min_production=min_prod,
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])

    with subtests.test("max_offtime_hours excludes long blocks from the multiplier"):
        # Profile has two off-blocks: one 1-hr (warm-qualifying) and one 4-hr
        # (cold-qualifying). With max_offtime_hours=3, the 4-hr block is excluded
        # so its following on-block is left at 1.0; the 1-hr block still triggers
        # a 1-hr delay.
        profile = np.array([rated, 0.0, rated, rated, 0.0, 0.0, 0.0, 0.0, rated, rated])
        mult = startup_loss_multiplier(
            profile,
            dt,
            offtime_hours=1.0,
            delay_hours=1.0,
            min_production=min_prod,
            max_offtime_hours=3.0,
        )
        # t=1 off (zero), t=2 warm delay (zero), t=4..7 off (zero), t=8..9 left
        # at 1.0 because the 4-hr block was excluded.
        assert np.allclose(mult, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0])

    with subtests.test("max_offtime_hours=None matches no upper bound"):
        profile = np.array([rated, 0.0, 0.0, 0.0, rated, rated])
        mult_no_max = startup_loss_multiplier(
            profile,
            dt,
            offtime_hours=1.0,
            delay_hours=1.0,
            min_production=min_prod,
        )
        mult_with_none = startup_loss_multiplier(
            profile,
            dt,
            offtime_hours=1.0,
            delay_hours=1.0,
            min_production=min_prod,
            max_offtime_hours=None,
        )
        assert np.allclose(mult_no_max, mult_with_none)

    with subtests.test("Off-block at start of profile zeros following delay window"):
        # An off-block that spans index 0 still triggers a start-up event on the
        # first on-step of the simulation.
        profile = np.array([0.0, 0.0, rated, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=1.0, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(mult, [0.0, 0.0, 0.0, 1.0, 1.0])

    with subtests.test("Off-block extending past end of profile contributes no startup loss"):
        # No on-step follows the trailing off-block, so the multiplier only
        # zeros the off-steps themselves.
        profile = np.array([rated, rated, 0.0, 0.0, 0.0])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=1.0, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 1.0, 0.0, 0.0, 0.0])

    with subtests.test("Profile fully off yields a fully zero multiplier"):
        profile = np.zeros(5)
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=1.0, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(mult, np.zeros(5))

    with subtests.test("Profile fully on yields a fully unit multiplier"):
        profile = np.full(5, rated)
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=1.0, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(mult, np.ones(5))

    with subtests.test("Multiple back-to-back qualifying off-blocks each trigger a delay"):
        # Two qualifying off-blocks each followed by an on-block long enough to
        # absorb the start-up delay -> each on-block loses its first delay step.
        profile = np.array([rated, 0.0, 0.0, rated, rated, 0.0, 0.0, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=2.0, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])

    with subtests.test("Single on-step between two qualifying off-blocks is fully zeroed"):
        # On-block of length 1 < total_delay_steps=2 -> entire on-step zeroed.
        profile = np.array([rated, 0.0, 0.0, rated, 0.0, 0.0, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=2.0, delay_hours=2.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    with subtests.test(
        "Warm + cold partition via two passes: each block triggers exactly one event"
    ):
        # warm pass handles 2..<5 hr off-blocks; cold pass handles >=5 hr.
        # Profile has a 2-hr off-block (warm) and a 5-hr off-block (cold).
        profile = np.array([rated, 0.0, 0.0, rated, rated, 0.0, 0.0, 0.0, 0.0, 0.0, rated, rated])
        m_warm = startup_loss_multiplier(
            profile,
            dt,
            offtime_hours=2.0,
            delay_hours=1.0,
            min_production=min_prod,
            max_offtime_hours=5.0,
        )
        m_cold = startup_loss_multiplier(
            profile,
            dt,
            offtime_hours=5.0,
            delay_hours=3.0,
            min_production=min_prod,
        )
        # Warm pass leaves the cold (5-hr) block's recovery at 1.0; cold pass
        # zeros the 3 hr after the long block. Their product gives the full
        # combined loss profile with no double-counting.
        assert np.allclose(
            m_warm,
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0],
        )
        assert np.allclose(
            m_cold,
            [1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        assert np.allclose(
            m_warm * m_cold,
            [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )

    with subtests.test(
        "max_offtime_hours==offtime_hours leaves warm pass with no qualifying blocks"
    ):
        # The off-block is exactly at the exclusion threshold (ceil convention),
        # so the warm pass excludes it; only the off-steps themselves are zeroed.
        profile = np.array([rated, 0.0, 0.0, rated])
        mult = startup_loss_multiplier(
            profile,
            dt,
            offtime_hours=1.0,
            delay_hours=1.0,
            min_production=min_prod,
            max_offtime_hours=1.0,
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 1.0])

    with subtests.test("Delay equal to one full timestep yields exactly one zero on-step"):
        # delay_hours/dt = 1 -> 1 full step + 0 partial.
        profile = np.array([rated, 0.0, 0.0, rated, rated, rated])
        mult = startup_loss_multiplier(
            profile, dt, offtime_hours=1.0, delay_hours=1.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 0.0, 0.0, 0.0, 1.0, 1.0])


@pytest.mark.unit
def test_dynamics_stacking(subtests):
    """Test stacked behaviors that mimic the ammonia synloop pipeline:

    request -> ``apply_ramping_limits`` -> ``startup_loss_multiplier`` ->
    ``apply_ramping_limits``.

    These tests exercise interactions between the per-step ramp limit, turndown
    floors, and warm/cold start-up losses that arise when the three primitives
    are composed.
    """
    dt = 3600.0
    rated = 10.0
    min_prod = 1.0

    with subtests.test("Cold-start delay is reinforced by a slow second ramp"):
        # Without the second ramp the profile would jump from 0 to rated after
        # the start-up delay; the slower second ramp re-introduces a gradual
        # recovery and also rate-limits the initial drop into the off-block.
        profile = np.array([rated, rated, 0.0, 0.0, 0.0, rated, rated, rated, rated])
        ramp1 = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=10.0,
            max_ramp_down_rate=10.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(ramp1, [10.0, 10.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0])

        mult = startup_loss_multiplier(
            ramp1, dt, offtime_hours=1.0, delay_hours=2.0, min_production=min_prod
        )
        assert np.allclose(mult, [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0])

        post_startup = mult * ramp1
        ramp2 = apply_ramping_limits(
            post_startup,
            dt,
            max_ramp_up_rate=2.0,
            max_ramp_down_rate=2.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        # The leading 10 -> 0 transition is rate-limited backward through
        # check_ramping_at_t0; the post-delay 0 -> 10 transition is forward-
        # limited by the slow ramp-up.
        assert np.allclose(ramp2, [4.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 4.0])

    with subtests.test("Sub-dt warm-start delay produces a fractional final step"):
        # delay_hours=0.5 with dt=1h -> a single partial on-step at multiplier
        # 0.5. The second ramp leaves it intact because the per-step delta is
        # within the rate.
        profile = np.array([rated, rated, 0.0, 0.0, rated, rated])
        ramp1 = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=10.0,
            max_ramp_down_rate=10.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        mult = startup_loss_multiplier(
            ramp1, dt, offtime_hours=1.0, delay_hours=0.5, min_production=min_prod
        )
        post_startup = mult * ramp1
        ramp2 = apply_ramping_limits(
            post_startup,
            dt,
            max_ramp_up_rate=10.0,
            max_ramp_down_rate=10.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(mult, [1.0, 1.0, 0.0, 0.0, 0.5, 1.0])
        assert np.allclose(post_startup, [10.0, 10.0, 0.0, 0.0, 5.0, 10.0])
        assert np.allclose(ramp2, [10.0, 10.0, 0.0, 0.0, 5.0, 10.0])

    with subtests.test("Turndown floor pre-zeros sub-minimum requests before ramping"):
        # Mimics the ammonia pipeline where any request below the turndown is
        # forced to zero before ``apply_ramping_limits`` is called. With a
        # generous ramp rate, the rest of the profile passes through unchanged.
        profile = np.array([10.0, 5.0, 2.0, 5.0, 10.0])
        turndown_min = 3.0
        preprocessed = np.where(profile < turndown_min, 0.0, profile)
        out = apply_ramping_limits(
            preprocessed,
            dt,
            max_ramp_up_rate=10.0,
            max_ramp_down_rate=10.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(preprocessed, [10.0, 5.0, 0.0, 5.0, 10.0])
        assert np.allclose(out, preprocessed)

    with subtests.test("Slow ramp limits recovery after a warm start"):
        # A 1-hr warm-start delay zeros one on-step after the off-block; the
        # post-startup profile then rises sharply, but the second ramp pass
        # rate-limits both the entry into the off-block and the recovery.
        profile = np.array([rated, rated, 0.0, 0.0, 0.0, rated, rated, rated, rated])
        ramp1 = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_rate=5.0,
            max_ramp_down_rate=5.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        mult = startup_loss_multiplier(
            ramp1, dt, offtime_hours=1.0, delay_hours=1.0, min_production=min_prod
        )
        post_startup = mult * ramp1
        ramp2 = apply_ramping_limits(
            post_startup,
            dt,
            max_ramp_up_rate=5.0,
            max_ramp_down_rate=5.0,
            commodity_rate_units="kg/h",
            commodity_amount_units="kg",
        )
        assert np.allclose(ramp1, [10.0, 5.0, 0.0, 0.0, 0.0, 5.0, 10.0, 10.0, 10.0])
        assert np.allclose(mult, [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
        assert np.allclose(post_startup, [10.0, 5.0, 0.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0])
        # The post-startup step from 0 -> 10 between i=5 and i=6 violates the
        # 5/hr ramp-up; the second pass clips it.
        assert np.allclose(ramp2, [10.0, 5.0, 0.0, 0.0, 0.0, 0.0, 5.0, 10.0, 10.0])
