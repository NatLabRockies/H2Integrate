import numpy as np
import pytest
import openmdao.api as om

from h2integrate.resource.tidal import TidalResource
from h2integrate.converters.water_power.tidal_pysam import PySAMTidalPerformanceModel


@pytest.fixture
def tidal_config():
    config = {
        "model_inputs": {
            "performance_parameters": {
                "device_rating_kw": 1115,  # [kW]
                "num_devices": 20,
                "tidal_power_curve": [
                    (0.0, 0.0),
                    (0.1, 0.0),
                    (0.2, 0.0),
                    (0.3, 0.0),
                    (0.4, 0.0),
                    (0.5, 0.0),
                    (0.6, 10.4211),
                    (0.7, 20.8423),
                    (0.8, 39.9689),
                    (0.9, 59.0956),
                    (1.0, 89.2016),
                    (1.1, 119.3080),
                    (1.2, 160.8860),
                    (1.3, 202.4640),
                    (1.4, 259.2920),
                    (1.5, 316.1200),
                    (1.6, 392.6730),
                    (1.7, 469.2260),
                    (1.8, 570.3060),
                    (1.9, 671.3860),
                    (2.0, 802.9080),
                    (2.1, 934.4300),
                    (2.2, 1024.7100),
                    (2.3, 1115.0000),
                    (2.4, 1115.0000),
                    (2.5, 1115.0000),
                    (2.6, 1115.0000),
                    (2.7, 1115.0000),
                    (2.8, 1115.0000),
                    (2.9, 1115.0000),
                    (3.0, 1115.0000),
                    (3.1, 1115.0000),
                    (3.2, 1085.3700),
                    (3.3, 1055.7300),
                ],
            }
        }
    }
    return config


@pytest.fixture
def pysam_options():
    pysam_options = {
        "MHKTidal": {
            "loss_array_spacing": 0.0,
            "loss_resource_overprediction": 0.0,
            "loss_transmission": 0.0,
            "loss_downtime": 0.0,
            "loss_additional": 0.0,
        }
    }
    return pysam_options


@pytest.fixture
def plant_config():
    plant_config = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
        "site": {
            "latitude": 47.5233,
            "longitude": -92.5366,
            "resources": {
                "tidal_resource": {
                    "resource_parameters": {
                        "resource_dir": "resource_files/tidal/",
                        "resource_filename": "Tidal_resource_timeseries.csv",
                    }
                }
            },
        },
    }
    return plant_config


@pytest.mark.unit
def test_tidal_pysam_outputs(plant_config, tidal_config, pysam_options, subtests):
    prob = om.Problem()

    tidal_resource = TidalResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["tidal_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("tidal_resource", tidal_resource, promotes=["*"])

    tidal_config["model_inputs"]["performance_parameters"]["pysam_options"] = pysam_options
    comp = PySAMTidalPerformanceModel(
        plant_config=plant_config,
        tech_config=tidal_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    commodity = "electricity"
    commodity_amount_units = "kW*h"
    commodity_rate_units = "kW"
    plant_life = int(plant_config["plant"]["plant_life"])
    n_timesteps = int(plant_config["plant"]["simulation"]["n_timesteps"])

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


@pytest.mark.unit
def test_tidal_performance_values(plant_config, tidal_config, pysam_options, subtests):
    """Add tests for values from performance model."""
    prob = om.Problem()

    tidal_resource = TidalResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["tidal_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("tidal_resource", tidal_resource, promotes=["*"])

    tidal_config["model_inputs"]["performance_parameters"]["pysam_options"] = pysam_options
    comp = PySAMTidalPerformanceModel(
        plant_config=plant_config,
        tech_config=tidal_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    # Test output values
    with subtests.test("electricity_out value"):
        assert (
            pytest.approx(np.sum(prob.get_val("comp.electricity_out", units="kW")), rel=1e-6)
            == 60625515.492
        )

    with subtests.test("rated_electricity_production value"):
        assert (
            pytest.approx(prob.get_val("comp.rated_electricity_production", units="kW"), rel=1e-6)
            == 1115 * 20
        )
    with subtests.test("total_electricity_produced value"):
        assert (
            pytest.approx(prob.get_val("comp.total_electricity_produced", units="kW*h"), rel=1e-6)
            == 60625515.492
        )
    with subtests.test("capacity_factor value"):
        assert (
            pytest.approx(prob.get_val("comp.capacity_factor", units="unitless"), rel=1e-6)
            == 0.310346
        )

    with subtests.test("annual_electricity_produced value"):
        assert (
            pytest.approx(
                prob.get_val("comp.annual_electricity_produced", units="kW*h/yr"), rel=1e-6
            )
            == 60625515.492
        )


@pytest.mark.unit
### Test run_recalculate_power_curve method
def test_recalculate_power_curve(plant_config, tidal_config, pysam_options, subtests):
    prob = om.Problem()

    tidal_resource = TidalResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["tidal_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("tidal_resource", tidal_resource, promotes=["*"])

    tidal_config["model_inputs"]["performance_parameters"]["pysam_options"] = pysam_options
    tidal_config["model_inputs"]["performance_parameters"]["run_recalculate_power_curve"] = True
    tidal_config["model_inputs"]["performance_parameters"]["device_rating_kw"] = (
        2230  # 2x the original rating
    )

    comp = PySAMTidalPerformanceModel(
        plant_config=plant_config,
        tech_config=tidal_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    device_rating_kw = 2230  # 2x the original rating

    with subtests.test("correctly runs in model"):
        # Check that the model runs with the recalculated power curve and produces expected outputs
        assert (
            pytest.approx(prob.get_val("comp.rated_electricity_production", units="kW"), rel=1e-6)
            == device_rating_kw * 20
        )

    with subtests.test("annual_electricity_produced value recalculated power curve"):
        assert (
            pytest.approx(
                prob.get_val("comp.annual_electricity_produced", units="kW*h/yr"), rel=1e-6
            )
            == 60625515.492 * 2
        )


@pytest.mark.unit
def test_tidal_default_model(plant_config, subtests):
    """Add tests for values from performance model."""
    prob = om.Problem()

    tidal_resource = TidalResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["tidal_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("tidal_resource", tidal_resource, promotes=["*"])

    tidal_config = {
        "model_inputs": {
            "performance_parameters": {
                "create_model_from": "default",
                "num_devices": 20,
                "device_rating_kw": 1115,
            }
        }
    }
    comp = PySAMTidalPerformanceModel(
        plant_config=plant_config,
        tech_config=tidal_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    # Test output values
    with subtests.test("electricity_out value"):
        assert (
            pytest.approx(np.sum(prob.get_val("comp.electricity_out", units="kW")), rel=1e-6)
            == 56381729.40755999
        )

    # test that it correctly adds the number of devices (overwriting PySAM json defaults)
    with subtests.test("rated_electricity_production value"):
        assert (
            pytest.approx(prob.get_val("comp.rated_electricity_production", units="kW"), rel=1e-6)
            == 1115 * 20
        )
    with subtests.test("total_electricity_produced value"):
        assert (
            pytest.approx(prob.get_val("comp.total_electricity_produced", units="kW*h"), rel=1e-6)
            == 56381729.40755999
        )
    with subtests.test("capacity_factor value"):
        assert (
            pytest.approx(prob.get_val("comp.capacity_factor", units="unitless"), rel=1e-6)
            == 0.28862199
        )

    with subtests.test("annual_electricity_produced value"):
        assert (
            pytest.approx(
                prob.get_val("comp.annual_electricity_produced", units="kW*h/yr"), rel=1e-6
            )
            == 56381729.40755999
        )
