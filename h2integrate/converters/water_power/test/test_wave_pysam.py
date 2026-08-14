import numpy as np
import pytest
import openmdao.api as om

from h2integrate.resource.wave import WaveResource
from h2integrate.converters.water_power.wave_pysam import (
    PySAMWavePerformanceModel,
    PySAMWavePerformanceConfig,
)


# Wave power matrix from the DOE Reference Model 3 (point absorber), 286 kW rated device.
# Rows: Hs bin centers [m] (first column) and power output [kW] at each Te bin.
# First row: Te bin centers [s].
WAVE_POWER_MATRIX = [
    [
        0.0,
        0.5,
        1.5,
        2.5,
        3.5,
        4.5,
        5.5,
        6.5,
        7.5,
        8.5,
        9.5,
        10.5,
        11.5,
        12.5,
        13.5,
        14.5,
        15.5,
        16.5,
        17.5,
        18.5,
        19.5,
        20.5,
    ],
    [
        0.25,
        0.0,
        0.0,
        0.0,
        0.0,
        0.4,
        0.6,
        0.8,
        1.0,
        1.1,
        1.1,
        1.0,
        0.8,
        0.7,
        0.6,
        0.5,
        0.4,
        0.3,
        0.3,
        0.2,
        0.2,
        0.0,
    ],
    [
        0.75,
        0.0,
        0.0,
        0.0,
        0.0,
        3.2,
        5.3,
        7.4,
        9.1,
        9.8,
        9.5,
        8.6,
        7.4,
        6.2,
        5.1,
        4.1,
        3.4,
        2.8,
        2.3,
        1.9,
        1.6,
        0.0,
    ],
    [
        1.25,
        0.0,
        0.0,
        0.0,
        0.0,
        9.0,
        14.8,
        20.5,
        25.0,
        26.8,
        25.9,
        23.3,
        20.0,
        16.8,
        13.8,
        11.3,
        9.2,
        7.6,
        6.3,
        5.2,
        4.3,
        0.0,
    ],
    [
        1.75,
        0.0,
        0.0,
        0.0,
        0.0,
        17.6,
        28.9,
        39.9,
        48.3,
        51.6,
        49.7,
        44.7,
        38.4,
        32.2,
        26.5,
        21.7,
        17.8,
        14.6,
        12.1,
        10.0,
        8.4,
        0.0,
    ],
    [
        2.25,
        0.0,
        0.0,
        0.0,
        0.0,
        29.0,
        47.5,
        65.4,
        78.8,
        83.8,
        80.6,
        72.4,
        62.3,
        52.2,
        43.0,
        35.3,
        28.9,
        23.8,
        19.7,
        16.3,
        13.7,
        0.0,
    ],
    [
        2.75,
        0.0,
        0.0,
        0.0,
        0.0,
        43.2,
        70.7,
        97.0,
        116.3,
        123.1,
        118.1,
        106.1,
        91.3,
        76.5,
        63.2,
        51.9,
        42.5,
        35.0,
        28.9,
        24.1,
        20.1,
        0.0,
    ],
    [
        3.25,
        0.0,
        0.0,
        0.0,
        0.0,
        60.2,
        98.3,
        134.5,
        160.5,
        169.3,
        162.1,
        145.5,
        125.2,
        105.0,
        86.8,
        71.3,
        58.5,
        48.2,
        39.9,
        33.2,
        27.8,
        0.0,
    ],
    [
        3.75,
        0.0,
        0.0,
        0.0,
        0.0,
        79.9,
        130.4,
        177.8,
        211.2,
        222.0,
        212.2,
        190.4,
        164.0,
        137.6,
        113.8,
        93.6,
        76.9,
        63.3,
        52.5,
        43.7,
        36.6,
        0.0,
    ],
    [
        4.25,
        0.0,
        0.0,
        0.0,
        0.0,
        102.4,
        166.7,
        226.7,
        268.3,
        281.1,
        268.2,
        240.5,
        207.2,
        174.1,
        144.1,
        118.5,
        97.4,
        80.3,
        66.6,
        55.5,
        46.5,
        0.0,
    ],
    [
        4.75,
        0.0,
        0.0,
        0.0,
        0.0,
        127.6,
        207.4,
        281.2,
        286.0,
        286.0,
        286.0,
        286.0,
        255.0,
        214.3,
        177.5,
        146.1,
        120.2,
        99.2,
        82.2,
        68.6,
        57.6,
        0.0,
    ],
    [
        5.25,
        0.0,
        0.0,
        0.0,
        0.0,
        155.4,
        252.4,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        258.2,
        214.0,
        176.3,
        145.1,
        119.8,
        99.4,
        83.0,
        69.7,
        0.0,
    ],
    [
        5.75,
        0.0,
        0.0,
        0.0,
        0.0,
        186.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        253.6,
        209.0,
        172.2,
        142.2,
        118.1,
        98.6,
        82.8,
        0.0,
    ],
    [
        6.25,
        0.0,
        0.0,
        0.0,
        0.0,
        219.2,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        244.2,
        201.2,
        166.4,
        138.2,
        115.5,
        97.1,
        0.0,
    ],
    [
        6.75,
        0.0,
        0.0,
        0.0,
        0.0,
        255.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        281.9,
        232.4,
        192.2,
        159.7,
        133.5,
        112.3,
        0.0,
    ],
    [
        7.25,
        0.0,
        0.0,
        0.0,
        0.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        265.6,
        219.8,
        182.8,
        152.9,
        128.7,
        0.0,
    ],
    [
        7.75,
        0.0,
        0.0,
        0.0,
        0.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        249.0,
        207.2,
        173.4,
        146.0,
        0.0,
    ],
    [
        8.25,
        0.0,
        0.0,
        0.0,
        0.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        279.9,
        233.0,
        195.1,
        164.4,
        0.0,
    ],
    [
        8.75,
        0.0,
        0.0,
        0.0,
        0.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        260.2,
        218.0,
        183.8,
        0.0,
    ],
    [
        9.25,
        0.0,
        0.0,
        0.0,
        0.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        242.1,
        204.1,
        0.0,
    ],
    [
        9.75,
        0.0,
        0.0,
        0.0,
        0.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        286.0,
        267.4,
        225.6,
        0.0,
    ],
]


@pytest.fixture
def wave_config():
    config = {
        "model_inputs": {
            "performance_parameters": {
                "device_rating_kw": 286,
                "num_devices": 108,
                "wave_power_matrix": WAVE_POWER_MATRIX,
                "resource_year": 2010,
            }
        }
    }
    return config


@pytest.fixture
def pysam_options():
    pysam_options = {
        "MHKWave": {
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
            "latitude": 43.807,
            "longitude": -124.816,
            "resources": {
                "wave_resource": {
                    "resource_parameters": {
                        "resource_dir": "resource_files/wave/",
                        "resource_filename": "wave_lat43.81_lon-124.82__2010.csv",
                        "resource_year": 2010,
                    }
                }
            },
        },
    }
    return plant_config


@pytest.mark.unit
def test_wave_pysam_outputs(plant_config, wave_config, pysam_options, subtests):
    prob = om.Problem()

    wave_resource = WaveResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wave_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("wave_resource", wave_resource, promotes=["*"])

    wave_config["model_inputs"]["performance_parameters"]["pysam_options"] = pysam_options
    comp = PySAMWavePerformanceModel(
        plant_config=plant_config,
        tech_config=wave_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    prob.run_model()

    commodity = "electricity"

    with subtests.test("electricity_out shape"):
        assert prob.get_val(f"comp.{commodity}_out").shape == (8760,)

    with subtests.test("electricity_out non-negative"):
        assert (prob.get_val(f"comp.{commodity}_out") >= 0).all()

    with subtests.test("rated_electricity_production"):
        assert prob.get_val("comp.rated_electricity_production") == pytest.approx(
            286 * 108, rel=1e-6
        )

    with subtests.test("mean electricity_out regression"):
        assert np.mean(prob.get_val(f"comp.{commodity}_out")) == pytest.approx(
            12586.456849, rel=1e-4
        )

    with subtests.test("total_electricity_produced regression"):
        assert prob.get_val("comp.total_electricity_produced")[0] == pytest.approx(
            110257362.0, rel=1e-4
        )

    with subtests.test("annual_electricity_produced regression"):
        assert prob.get_val("comp.annual_electricity_produced")[0] == pytest.approx(
            110257362.0, rel=1e-4
        )

    with subtests.test("capacity_factor regression"):
        assert float(prob.get_val("comp.capacity_factor").flat[0]) == pytest.approx(
            0.407487, rel=1e-4
        )


@pytest.mark.unit
def test_wave_pysam_config_validation(subtests):
    with subtests.test("missing wave_power_matrix"):
        with pytest.raises(ValueError, match="wave_power_matrix"):
            PySAMWavePerformanceConfig.from_dict(
                {
                    "device_rating_kw": 286,
                    "num_devices": 108,
                }
            )

    with subtests.test("invalid pysam_options group"):
        with pytest.raises(ValueError, match="Invalid group"):
            PySAMWavePerformanceConfig.from_dict(
                {
                    "device_rating_kw": 286,
                    "num_devices": 108,
                    "wave_power_matrix": WAVE_POWER_MATRIX,
                    "pysam_options": {"InvalidGroup": {}},
                }
            )

    with subtests.test("number_devices in pysam_options raises"):
        with pytest.raises(ValueError, match="number_devices"):
            PySAMWavePerformanceConfig.from_dict(
                {
                    "device_rating_kw": 286,
                    "num_devices": 108,
                    "wave_power_matrix": WAVE_POWER_MATRIX,
                    "pysam_options": {"MHKWave": {"number_devices": 5}},
                }
            )


@pytest.mark.unit
def test_wave_resource_output_shape(plant_config, subtests):
    prob = om.Problem()

    wave_resource = WaveResource(
        plant_config=plant_config,
        resource_config=plant_config["site"]["resources"]["wave_resource"]["resource_parameters"],
        driver_config={},
    )

    prob.model.add_subsystem("wave_resource", wave_resource, promotes=["*"])
    prob.setup()
    prob.run_model()

    with subtests.test("significant_wave_height shape"):
        assert prob.get_val("significant_wave_height").shape == (8760,)

    with subtests.test("energy_period shape"):
        assert prob.get_val("energy_period").shape == (8760,)

    with subtests.test("significant_wave_height positive"):
        assert (prob.get_val("significant_wave_height") > 0).all()

    with subtests.test("energy_period positive"):
        assert (prob.get_val("energy_period") > 0).all()
