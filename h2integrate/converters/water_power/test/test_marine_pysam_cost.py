import pytest
import openmdao.api as om

from h2integrate.resource.tidal import TidalResource
from h2integrate.converters.water_power.tidal_pysam import PySAMTidalPerformanceModel
from h2integrate.converters.water_power.pysam_marine_cost import PySAMMarineCostModel


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


@pytest.fixture
def cost_config():
    cost_config = {
        "model_inputs": {
            "cost_parameters": {
                "device_rating_kw": 1115,
                "num_devices": 20,
                "reference_model_number": 1,
                "water_depth": 100,
                "distance_to_shore": 80,
                "number_rows": 2,
                "device_spacing": 600,
                "row_spacing": 600,
                "cable_system_overbuild": 20,
            }
        }
    }
    return cost_config


# Loop through reference model number and test capex and opex values
@pytest.mark.unit
def test_ref_model_number1(cost_config, plant_config, subtests):
    prob = om.Problem()

    cost = PySAMMarineCostModel(
        plant_config=plant_config,
        tech_config=cost_config,
        driver_config={},
    )

    prob.model.add_subsystem("cost", cost, promotes=["*"])
    prob.setup()

    prob.run_model()

    with subtests.test("RM1 Capex"):
        assert (
            pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6) == 123902868.62743238
        )

    with subtests.test("RM1 Opex"):
        assert pytest.approx(prob.get_val("cost.OpEx", units="USD/year"), rel=1e-6) == 4498582.9


@pytest.mark.unit
def test_ref_model_number2(cost_config, plant_config, subtests):
    prob = om.Problem()

    cost_config["model_inputs"]["cost_parameters"]["reference_model_number"] = 2
    cost = PySAMMarineCostModel(
        plant_config=plant_config,
        tech_config=cost_config,
        driver_config={},
    )

    prob.model.add_subsystem("cost", cost, promotes=["*"])
    prob.setup()

    prob.run_model()

    with subtests.test("RM2 Capex"):
        assert (
            pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6) == 194855694.06743234
        )

    with subtests.test("RM2 Opex"):
        assert pytest.approx(prob.get_val("cost.OpEx", units="USD/year"), rel=1e-6) == 4498582.9


@pytest.mark.unit
def test_ref_model_number3(cost_config, plant_config, subtests):
    prob = om.Problem()

    cost_config["model_inputs"]["cost_parameters"]["reference_model_number"] = 3
    cost = PySAMMarineCostModel(
        plant_config=plant_config,
        tech_config=cost_config,
        driver_config={},
    )

    prob.model.add_subsystem("cost", cost, promotes=["*"])
    prob.setup()

    prob.run_model()

    with subtests.test("RM3 Capex"):
        assert (
            pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6) == 366034529.39826673
        )

    with subtests.test("RM3 Opex"):
        assert pytest.approx(prob.get_val("cost.OpEx", units="USD/year"), rel=1e-6) == 4498582.9


@pytest.mark.unit
def test_ref_model_number5(cost_config, plant_config, subtests):
    prob = om.Problem()

    cost_config["model_inputs"]["cost_parameters"]["reference_model_number"] = 5
    cost = PySAMMarineCostModel(
        plant_config=plant_config,
        tech_config=cost_config,
        driver_config={},
    )

    prob.model.add_subsystem("cost", cost, promotes=["*"])
    prob.setup()

    prob.run_model()

    with subtests.test("RM5 Capex"):
        assert (
            pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6) == 366895942.95049995
        )

    with subtests.test("RM5 Opex"):
        assert pytest.approx(prob.get_val("cost.OpEx", units="USD/year"), rel=1e-6) == 4498582.9


@pytest.mark.unit
def test_ref_model_number6(cost_config, plant_config, subtests):
    prob = om.Problem()

    cost_config["model_inputs"]["cost_parameters"]["reference_model_number"] = 6
    cost = PySAMMarineCostModel(
        plant_config=plant_config,
        tech_config=cost_config,
        driver_config={},
    )

    prob.model.add_subsystem("cost", cost, promotes=["*"])
    prob.setup()

    prob.run_model()

    with subtests.test("RM6 Capex"):
        assert pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6) == 580646799.6967537

    with subtests.test("RM6 Opex"):
        assert pytest.approx(prob.get_val("cost.OpEx", units="USD/year"), rel=1e-6) == 4498582.9


@pytest.mark.unit
def test_custom_cost(cost_config, plant_config, subtests):
    prob = om.Problem()

    cost_config["model_inputs"]["cost_parameters"]["pysam_cost_options"] = {
        "MHKCosts": {
            "structural_assembly_cost_input": 20,  # $/kw
            "structural_assembly_cost_method": 0,  # Enter in $/kw
        }
    }
    cost = PySAMMarineCostModel(
        plant_config=plant_config,
        tech_config=cost_config,
        driver_config={},
    )

    prob.model.add_subsystem("cost", cost, promotes=["*"])
    prob.setup()

    prob.run_model()

    with subtests.test("capex is not equal to RM1 capex"):
        assert (
            pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6)
            != 123902868.62743238  # Value from test_ref_model_number1 subtest [RM1 Capex]
        )
    with subtests.test("Adjusted RM1 Capex"):
        assert (
            pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6) == 122936916.35143237
        )


@pytest.mark.integration
def test_performance_cost_with_pysam_options(plant_config, cost_config, subtests):
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
                "pysam_options": {
                    "MHKTidal": {
                        "loss_downtime": 10.0,
                    }
                },
            }
        }
    }
    comp = PySAMTidalPerformanceModel(
        plant_config=plant_config,
        tech_config=tidal_config,
        driver_config={},
    )
    prob.model.add_subsystem("comp", comp, promotes=["*"])

    cost_config["model_inputs"]["cost_parameters"]["pysam_cost_options"] = {
        "MHKCosts": {
            "structural_assembly_cost_input": 20,  # $/kw
            "structural_assembly_cost_method": 0,  # Enter in $/kw
        }
    }
    cost = PySAMMarineCostModel(
        plant_config=plant_config,
        tech_config=cost_config,
        driver_config={},
    )

    prob.model.add_subsystem("cost", cost, promotes=["*"])
    prob.setup()

    prob.run_model()
    with subtests.test("total_electricity_produced value"):
        assert (
            pytest.approx(prob.get_val("comp.total_electricity_produced", units="kW*h"), rel=1e-6)
            == 51531688.16819879
        )

    with subtests.test("capex is not equal to RM1 capex"):
        assert (
            pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6)
            != 123902868.62743238  # Value from test_ref_model_number1 subtest [RM1 Capex]
        )
    with subtests.test("Adjusted RM1 Capex"):
        assert (
            pytest.approx(prob.get_val("cost.CapEx", units="USD"), rel=1e-6) == 122936916.35143237
        )


@pytest.mark.unit
def test_rows_and_device_error(cost_config, plant_config):
    prob = om.Problem()

    msg = "number_of_rows exceeds num_devices"
    with pytest.raises(Exception, match=msg):
        cost_config["model_inputs"]["cost_parameters"]["number_rows"] = 100
        cost = PySAMMarineCostModel(
            plant_config=plant_config,
            tech_config=cost_config,
            driver_config={},
        )

        prob.model.add_subsystem("cost", cost, promotes=["*"])
        prob.setup()

        prob.run_model()


@pytest.mark.unit
def test_layout_error(cost_config, plant_config):
    prob = om.Problem()
    msg = "Layout must be square or rectangular. Modify 'number_rows' or 'num_devices'."
    with pytest.raises(Exception, match=msg):
        cost_config["model_inputs"]["cost_parameters"]["num_devices"] = 25
        cost = PySAMMarineCostModel(
            plant_config=plant_config,
            tech_config=cost_config,
            driver_config={},
        )

        prob.model.add_subsystem("cost", cost, promotes=["*"])
        prob.setup()

        prob.run_model()
