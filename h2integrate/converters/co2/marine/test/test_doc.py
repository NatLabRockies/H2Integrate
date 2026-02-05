import numpy as np
import pytest
import openmdao.api as om
from openmdao.utils.assert_utils import assert_near_equal

from h2integrate.converters.co2.marine.direct_ocean_capture import DOCPerformanceModel


has_mcm = True
try:
    import mcm  # noqa: F401
except ModuleNotFoundError:
    has_mcm = False


@pytest.mark.unit
@pytest.mark.skipif(not has_mcm, reason="mcm is not installed")
def test_doc_outputs(driver_config, plant_config, tech_config, subtests):
    doc_model = DOCPerformanceModel(
        driver_config=driver_config, plant_config=plant_config, tech_config=tech_config
    )
    prob = om.Problem(model=om.Group())
    prob.model.add_subsystem("comp", doc_model, promotes=["*"])
    prob.setup()
    rng = np.random.default_rng(seed=42)
    base_power = np.linspace(3.0e8, 2.0e8, 8760)  # 5 MW to 10 MW over 8760 hours
    noise = rng.normal(loc=0, scale=0.5e8, size=8760)  # ±0.5 MW noise
    power_profile = base_power + noise
    prob.set_val("comp.electricity_in", power_profile, units="W")

    # Run the model
    prob.run_model()

    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

    commodity = "co2"
    commodity_amount_units = "kg"
    commodity_rate_units = "kg/h"

    # Check that replacement schedule is between 0 and 1
    with subtests.test("0 <= replacement_schedule <=1"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") <= 1)

    with subtests.test("replacement_schedule length"):
        assert len(prob.get_val("comp.replacement_schedule", units="unitless")) == plant_life

    # Check that capacity factor is between 0 and 1 with units of "unitless"
    with subtests.test("0 <= capacity_factor (unitless) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") >= 0)
        assert np.all(prob.get_val("comp.capacity_factor", units="unitless") <= 1)

    # Check that capacity factor is between 1 and 100 with units of "percent"
    with subtests.test("1 <= capacity_factor (percent) <=1"):
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") >= 1)
        assert np.all(prob.get_val("comp.capacity_factor", units="percent") <= 100)

    with subtests.test("capacity_factor length"):
        assert len(prob.get_val("comp.capacity_factor", units="unitless")) == plant_life

    # Test that rated commodity production is greater than zero
    with subtests.test(f"rated_{commodity}_production > 0"):
        assert np.all(
            prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units) > 0
        )

    with subtests.test(f"rated_{commodity}_production length"):
        assert (
            len(prob.get_val(f"comp.rated_{commodity}_production", units=commodity_rate_units)) == 1
        )

    # Test that total commodity production is greater than zero
    with subtests.test(f"total_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units) > 0
        )
    with subtests.test(f"total_{commodity}_produced length"):
        assert (
            len(prob.get_val(f"comp.total_{commodity}_produced", units=commodity_amount_units)) == 1
        )

    # Test that annual commodity production is greater than zero
    with subtests.test(f"annual_{commodity}_produced > 0"):
        assert np.all(
            prob.get_val(f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr")
            > 0
        )

    with subtests.test(f"annual_{commodity}_produced[1:] == annual_{commodity}_produced[0]"):
        annual_production = prob.get_val(
            f"comp.annual_{commodity}_produced", units=f"{commodity_amount_units}/yr"
        )
        assert np.all(annual_production[1:] == annual_production[0])

    with subtests.test(f"annual_{commodity}_produced length"):
        assert len(annual_production) == plant_life

    # Test that commodity output has some values greater than zero
    with subtests.test(f"Some of {commodity}_out > 0"):
        assert np.any(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units) > 0)

    with subtests.test(f"{commodity}_out length"):
        assert len(prob.get_val(f"comp.{commodity}_out", units=commodity_rate_units)) == n_timesteps

    # Test default values
    with subtests.test("operational_life default value"):
        assert prob.get_val("comp.operational_life", units="yr") == plant_life
    with subtests.test("replacement_schedule value"):
        assert np.all(prob.get_val("comp.replacement_schedule", units="unitless") == 0)


@pytest.mark.regression
@pytest.mark.skipif(not has_mcm, reason="mcm is not installed")
def test_performance_model(tech_config, plant_config, driver_config):
    doc_model = DOCPerformanceModel(
        driver_config=driver_config, plant_config=plant_config, tech_config=tech_config
    )
    prob = om.Problem(model=om.Group())
    prob.model.add_subsystem("DOC", doc_model, promotes=["*"])
    prob.setup()

    # Set inputs
    rng = np.random.default_rng(seed=42)
    base_power = np.linspace(3.0e8, 2.0e8, 8760)  # 5 MW to 10 MW over 8760 hours
    noise = rng.normal(loc=0, scale=0.5e8, size=8760)  # ±0.5 MW noise
    power_profile = base_power + noise
    prob.set_val("DOC.electricity_in", power_profile, units="W")

    # Run the model
    prob.run_model()

    # Additional asserts for output values
    co2_out = prob.get_val("co2_out")
    co2_capture_mtpy = prob.get_val("co2_capture_mtpy")
    plant_mCC_capacity_mtph = prob.get_val("plant_mCC_capacity_mtph")
    total_tank_volume_m3 = prob.get_val("total_tank_volume_m3")

    # Assert values (allowing for small numerical tolerance)
    assert_near_equal(np.linalg.norm(co2_out), 11394970.06218, tolerance=1e-1)
    assert_near_equal(np.linalg.norm(co2_capture_mtpy), [1041164.44000004], tolerance=1e-5)
    assert_near_equal(plant_mCC_capacity_mtph, [176.34], tolerance=1e-2)
    assert_near_equal(total_tank_volume_m3, [25920.0], tolerance=1e-2)


@pytest.mark.skipif(has_mcm, reason="mcm is installed")
@pytest.mark.unit
def test_no_mcm_import(tech_config, plant_config, driver_config):
    err = "The `mcm` package is required to use the Direct Ocean Capture model. Install it via:"
    with pytest.raises(match=err):
        DOCPerformanceModel(
            driver_config=driver_config, plant_config=plant_config, tech_config=tech_config
        )
