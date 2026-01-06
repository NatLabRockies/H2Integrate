import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.hydrogen.h2_storage_cost import (
    PipeStorageCostModel,
    SaltCavernStorageCostModel,
    LinedRockCavernStorageCostModel,
)


@fixture
def plant_config():
    plant_config_dict = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,  # Default number of timesteps for the simulation
            },
        },
    }
    return plant_config_dict


def test_salt_cavern_ex_2(plant_config, subtests):
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 3580383.39133725,
                "max_charge_rate": 12549.62622698,
            }
        }
    }
    prob = om.Problem()
    comp = SaltCavernStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == 65337437.17944019
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-6) == 3149096.037312646
    with subtests.test("VarOpEx"):
        assert pytest.approx(np.sum(prob.get_val("sys.VarOpEx")), rel=1e-6) == 0.0
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2018


def test_lined_rock_cavern_ex_12_small_case(plant_config, subtests):
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 169320.79994693,
                "max_charge_rate": 1568.70894716,
            }
        }
    }
    prob = om.Problem()

    comp = LinedRockCavernStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == 18693728.23242369
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-6) == 1099582.4333529277
    with subtests.test("VarOpEx"):
        assert pytest.approx(np.sum(prob.get_val("sys.VarOpEx")), rel=1e-6) == 0.0
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2018


def test_lined_rock_cavern_ex_1(plant_config, subtests):
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 2081385.93267781,
                "max_charge_rate": 14118.14678877,
            }
        }
    }
    prob = om.Problem()
    comp = LinedRockCavernStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == 92392496.03198986
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-6) == 4292680.718474801
    with subtests.test("VarOpEx"):
        assert pytest.approx(np.sum(prob.get_val("sys.VarOpEx")), rel=1e-6) == 0.0
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2018


def test_lined_rock_cavern_ex_14(plant_config, subtests):
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 2987042.0,
                "max_charge_rate": 12446.00729773,
            }
        }
    }
    prob = om.Problem()
    comp = LinedRockCavernStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == 1.28437699 * 1e8
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-6) == 5315184.827689768
    with subtests.test("VarOpEx"):
        assert pytest.approx(np.sum(prob.get_val("sys.VarOpEx")), rel=1e-6) == 0.0
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2018


def test_buried_pipe_storage(plant_config, subtests):
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 3580383.39133725,
                "max_charge_rate": 12549.62622698,
            }
        }
    }
    prob = om.Problem()
    comp = PipeStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == 1827170156.1390543
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-6) == 57720829.60694359
    with subtests.test("VarOpEx"):
        assert pytest.approx(np.sum(prob.get_val("sys.VarOpEx")), rel=1e-6) == 0.0
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2018


def test_lined_rock_cavern_capex_per_kg(plant_config):
    """Test based on original test_lined_rock_storage.py with 1M kg storage capacity."""
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 1000000,
                "max_charge_rate": 100000 / 24,  # 100000 kg/day converted to kg/h
            }
        }
    }
    prob = om.Problem()
    comp = LinedRockCavernStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    # Calculate expected capex per kg
    h2_storage_kg = 1000000
    a = 0.095803
    b = 1.5868
    c = 10.332
    capex_per_kg = np.exp(
        a * (np.log(h2_storage_kg / 1000)) ** 2 - b * np.log(h2_storage_kg / 1000) + c
    )
    cepci_overall = 1.29 / 1.30
    expected_capex = cepci_overall * capex_per_kg * h2_storage_kg

    assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == expected_capex


def test_lined_rock_cavern_1M_kg(plant_config, subtests):
    """Test lined rock cavern with 1M kg capacity matching original unit tests."""
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 1000000,
                "max_charge_rate": 100000 / 24,  # 100000 kg/day converted to kg/h
            }
        }
    }
    prob = om.Problem()
    comp = LinedRockCavernStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-5) == 51136144.673
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-5) == 2359700.44640052
    with subtests.test("VarOpEx"):
        assert pytest.approx(np.sum(prob.get_val("sys.VarOpEx")), rel=1e-6) == 0.0
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2018


def test_salt_cavern_capex_per_kg(plant_config):
    """Test based on original test_salt_cavern_storage.py with 1M kg storage capacity."""
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 1000000,
                "max_charge_rate": 100000 / 24,  # 100000 kg/day converted to kg/h
            }
        }
    }
    prob = om.Problem()
    comp = SaltCavernStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    # Calculate expected capex per kg
    h2_storage_kg = 1000000
    a = 0.092548
    b = 1.6432
    c = 10.161
    capex_per_kg = np.exp(
        a * (np.log(h2_storage_kg / 1000)) ** 2 - b * np.log(h2_storage_kg / 1000) + c
    )
    cepci_overall = 1.29 / 1.30
    expected_capex = cepci_overall * capex_per_kg * h2_storage_kg

    assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == expected_capex


def test_salt_cavern_1M_kg(plant_config, subtests):
    """Test salt cavern with 1M kg capacity matching original unit tests."""
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 1000000,
                "max_charge_rate": 100000 / 24,  # 100000 kg/day converted to kg/h
            }
        }
    }
    prob = om.Problem()
    comp = SaltCavernStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-5) == 24992482.4198
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-5) == 1461663.9089168755
    with subtests.test("VarOpEx"):
        assert pytest.approx(np.sum(prob.get_val("sys.VarOpEx")), rel=1e-6) == 0.0
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2018


def test_pipe_storage_capex_per_kg(plant_config):
    """Test based on original test_underground_pipe_storage.py with 1M kg storage capacity."""
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 1000000,
                "max_charge_rate": 100000 / 24,  # 100000 kg/day converted to kg/h
            }
        }
    }
    prob = om.Problem()
    comp = PipeStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    # Calculate expected capex per kg
    h2_storage_kg = 1000000
    a = 0.0041617
    b = 0.060369
    c = 6.4581
    capex_per_kg = np.exp(
        a * (np.log(h2_storage_kg / 1000)) ** 2 - b * np.log(h2_storage_kg / 1000) + c
    )
    cepci_overall = 1.29 / 1.30
    expected_capex = cepci_overall * capex_per_kg * h2_storage_kg

    assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == expected_capex


def test_pipe_storage_1M_kg(plant_config, subtests):
    """Test underground pipe storage with 1M kg capacity matching original unit tests."""
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": 1000000,
                "max_charge_rate": 100000 / 24,  # 100000 kg/day converted to kg/h
            }
        }
    }
    prob = om.Problem()
    comp = PipeStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.run_model()

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-5) == 508745483.851
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-5) == 16439748.432128396
    with subtests.test("VarOpEx"):
        assert pytest.approx(np.sum(prob.get_val("sys.VarOpEx")), rel=1e-6) == 0.0
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2018
