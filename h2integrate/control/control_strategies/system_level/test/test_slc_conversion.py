"""Hand-calculable conversion-ratio tests for system-level control."""

import numpy as np
import pytest

from h2integrate.control.control_strategies.system_level.slc_topology import ConversionLink
from h2integrate.control.control_strategies.system_level.slc_conversion import (
    capacity_ratio,
    measured_ratio,
    conversion_ratio,
    accumulate_derived_demand,
)


@pytest.mark.unit
def test_capacity_ratio(subtests):
    with subtests.test("Appendix A Haber-Bosch electricity seed"):
        assert capacity_ratio([500.0], [], 1000.0) == pytest.approx(0.5)

    with subtests.test("the old lumped suppliers would seed a ratio of 2.0"):
        assert capacity_ratio([500.0, 1500.0], [], 1000.0) == pytest.approx(2.0)

    with subtests.test("feedstock capacity uses its mean supply"):
        assert capacity_ratio([70.0], [np.array([20.0, 40.0])], 50.0) == pytest.approx(2.0)

    with subtests.test("zero rated output has no capacity seed"):
        assert capacity_ratio([500.0], [], 0.0) is None


@pytest.mark.unit
def test_measured_ratio_round_numbers(subtests):
    with subtests.test("electrolyzer consumes 5500 kW for 100 kg/h hydrogen"):
        result = measured_ratio(np.full(4, 5500.0), np.full(4, 100.0), fallback=51.0)
        np.testing.assert_array_equal(result, np.full(4, 55.0))

    with subtests.test("time-varying ratios are preserved per timestep"):
        result = measured_ratio([5000.0, 5500.0, 6000.0], [100.0, 100.0, 100.0], fallback=1.0)
        np.testing.assert_array_equal(result, [50.0, 55.0, 60.0])


@pytest.mark.unit
def test_conversion_ratio_uses_capacity_only_at_zero_output():
    ratios, sources = conversion_ratio(
        consumed=[5000.0, 5500.0, 9999.0],
        produced=[100.0, 100.0, 0.0],
        fallback=55.0,
    )

    np.testing.assert_array_equal(ratios, [50.0, 55.0, 55.0])
    np.testing.assert_array_equal(sources, ["measured", "measured", "capacity"])


@pytest.mark.unit
def test_conversion_ratio_uses_capacity_for_nan_sentinel():
    ratios, sources = conversion_ratio(
        consumed=np.full(4, np.nan), produced=np.full(4, 100.0), fallback=0.5
    )

    np.testing.assert_array_equal(ratios, np.full(4, 0.5))
    np.testing.assert_array_equal(sources, np.full(4, "capacity"))


@pytest.mark.unit
def test_conversion_ratio_chain_matches_recipe_product():
    hydrogen_per_ammonia = measured_ratio([18.0], [100.0], fallback=1.0)[0]
    electricity_per_hydrogen = measured_ratio([990.0], [18.0], fallback=1.0)[0]

    assert 100.0 * hydrogen_per_ammonia * electricity_per_hydrogen == pytest.approx(990.0)


@pytest.mark.unit
def test_accumulate_derived_demand_does_not_mutate_inputs():
    in_bus = "natural_gas:reformer"
    derived_demand = {in_bus: np.array([100.0, 200.0])}
    contributions = {in_bus: {"reformer": np.array([30.0, 50.0])}}
    original_demand = derived_demand[in_bus].copy()
    original_contribution = contributions[in_bus]["reformer"].copy()
    link = ConversionLink(
        in_commodity="natural_gas",
        tech="reformer",
        out_commodity="hydrogen",
        in_bus=in_bus,
        out_bus="hydrogen:haber_bosch",
    )

    updated_demand, updated_contributions = accumulate_derived_demand(
        derived_demand,
        contributions,
        link,
        set_point=[10.0, 20.0],
        ratio=[2.0, 4.0],
    )

    np.testing.assert_array_equal(derived_demand[in_bus], original_demand)
    np.testing.assert_array_equal(contributions[in_bus]["reformer"], original_contribution)
    assert updated_demand is not derived_demand
    assert updated_contributions is not contributions
    np.testing.assert_array_equal(updated_demand[in_bus], [100.0, 230.0])
    np.testing.assert_array_equal(updated_contributions[in_bus]["reformer"], [30.0, 80.0])
