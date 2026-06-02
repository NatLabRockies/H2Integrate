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


@pytest.mark.unit
def test_apply_ramping_limits(subtests):
    dt = 3600.0  # 1 hour
    rate_up = 2.0
    rate_down = 1.0

    with subtests.test("In-bounds steps pass through unchanged"):
        profile = np.array([0.0, 1.0, 2.0, 1.5])
        out = apply_ramping_limits(
            profile, dt, rate_up, rate_down, min_production=0.0, max_production=10.0
        )
        assert np.allclose(out, profile)

    with subtests.test("Up-ramp clipped to max rate per step"):
        profile = np.array([0.0, 10.0, 10.0])
        out = apply_ramping_limits(
            profile, dt, rate_up, rate_down, min_production=0.0, max_production=10.0
        )
        # Step 1: 0 -> requested 10, capped at +2 -> 2. Step 2: 2 -> requested 10, capped -> 4.
        assert np.allclose(out, [0.0, 2.0, 4.0])

    with subtests.test("Down-ramp clipped to max rate per step"):
        profile = np.array([10.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile, dt, rate_up, rate_down, min_production=0.0, max_production=10.0
        )
        # Step 1: 10 -> requested 0, capped at -1 -> 9. Step 2: 9 -> 0, capped -> 8.
        assert np.allclose(out, [10.0, 9.0, 8.0])

    with subtests.test("Per-step delta scales with dt"):
        profile = np.array([0.0, 10.0, 10.0])
        out = apply_ramping_limits(
            profile,
            dt_seconds=1800.0,
            max_ramp_up_per_hr=rate_up,
            max_ramp_down_per_hr=rate_down,
            min_production=0.0,
            max_production=10.0,
        )
        # dt_hours = 0.5, max_up_per_step = 1.0
        assert np.allclose(out, [0.0, 1.0, 2.0])

    with subtests.test("Ramp-limited steps are clipped to [min, max]"):
        # Down-ramping toward 0 below min_production=2: steps clipped to min.
        profile = np.array([5.0, 0.0, 0.0, 0.0])
        out = apply_ramping_limits(
            profile,
            dt,
            max_ramp_up_per_hr=10.0,
            max_ramp_down_per_hr=1.0,
            min_production=2.0,
            max_production=10.0,
        )
        # 5 -> 4 -> 3 -> clip(2, 2, 10) = 2
        assert np.allclose(out, [5.0, 4.0, 3.0, 2.0])

    with subtests.test("First timestep is taken from input unchanged"):
        profile = np.array([7.5, 7.5])
        out = apply_ramping_limits(
            profile, dt, rate_up, rate_down, min_production=0.0, max_production=10.0
        )
        assert out[0] == 7.5


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
