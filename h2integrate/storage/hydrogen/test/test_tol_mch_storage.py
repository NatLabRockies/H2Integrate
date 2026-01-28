import numpy as np
import pytest
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.storage.hydrogen.mch_storage import MCHTOLStorageCostModel


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


def test_mch_wrapper(plant_config, subtests):
    Dc_tpd = 304
    Hc_tpd = 304
    As_tpy = 35000
    Ms_tpy = 16200

    toc_actual = 639375591
    foc_actual = 10239180
    voc_actual = 17332229

    max_cost_error_rel = 0.06

    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": Ms_tpy * 1e3,
                "max_charge_rate": Hc_tpd * 1e3 / 24,
                "max_discharge_rate": Dc_tpd * 1e3 / 24,
                "charge_equals_discharge": False,
            }
        }
    }

    target_annual_h2_stored = As_tpy * 1e3
    storage_capacity_kg = Ms_tpy * 1e3
    n_fills = target_annual_h2_stored / storage_capacity_kg
    fill_ratio_per_hr = n_fills / (8760 / 2)
    fill_per_hr = fill_ratio_per_hr * storage_capacity_kg
    soc = np.tile([fill_per_hr / storage_capacity_kg, 0], 4380)
    prob = om.Problem()
    comp = MCHTOLStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.set_val("sys.hydrogen_soc", soc)
    prob.run_model()

    with subtests.test("Dehydrogenation capacity"):
        assert comp.Dc == approx(Dc_tpd, rel=1e-6)
    with subtests.test("Hydrogenation capacity"):
        assert comp.Hc == approx(Hc_tpd, rel=1e-6)
    with subtests.test("Annual storage capacity"):
        assert comp.As == approx(As_tpy, rel=1e-6)
    with subtests.test("Maximum storage capacity"):
        assert comp.Ms == approx(Ms_tpy, rel=1e-6)
    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=max_cost_error_rel) == toc_actual
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=max_cost_error_rel) == foc_actual
    with subtests.test("VarOpEx"):
        assert pytest.approx(prob.get_val("sys.VarOpEx"), rel=max_cost_error_rel) == voc_actual
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2024


def test_mch_wrapper_ex1(plant_config, subtests):
    # Ran Example 1 with MCH storage
    # Annual H2 Stored: 17878378.49459929

    target_annual_h2_stored_kg = 17878378.49459929
    storage_capacity_kg = 2081385.9326778147
    charge_rate_kg_pr_hr = 3342.322748213135  # 14118.146788766157
    discharge_rate_kg_pr_hr = 10775.824040553021
    tech_config_dict = {
        "model_inputs": {
            "shared_parameters": {
                "max_capacity": storage_capacity_kg,
                "max_charge_rate": charge_rate_kg_pr_hr,
                "max_discharge_rate": discharge_rate_kg_pr_hr,
                "charge_equals_discharge": False,
            }
        }
    }

    n_fills = target_annual_h2_stored_kg / storage_capacity_kg
    fill_ratio_per_hr = n_fills / (8760 / 2)
    fill_per_hr = fill_ratio_per_hr * storage_capacity_kg
    soc = np.tile([fill_per_hr / storage_capacity_kg, 0], 4380)
    prob = om.Problem()
    comp = MCHTOLStorageCostModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
        driver_config={},
    )
    prob.model.add_subsystem("sys", comp)
    prob.setup()
    prob.set_val("sys.hydrogen_soc", soc)
    prob.run_model()

    with subtests.test("Dehydrogenation capacity"):
        assert comp.Dc == approx(discharge_rate_kg_pr_hr * 24 / 1e3, rel=1e-6)
    with subtests.test("Hydrogenation capacity"):
        assert comp.Hc == approx(charge_rate_kg_pr_hr * 24 / 1e3, rel=1e-6)
    with subtests.test("Annual storage capacity"):
        assert comp.As == approx(target_annual_h2_stored_kg / 1e3, rel=1e-6)
    with subtests.test("Maximum storage capacity"):
        assert comp.Ms == approx(storage_capacity_kg / 1e3, rel=1e-6)

    with subtests.test("CapEx"):
        assert pytest.approx(prob.get_val("sys.CapEx")[0], rel=1e-6) == 2.62304217 * 1e8
    with subtests.test("OpEx"):
        assert pytest.approx(prob.get_val("sys.OpEx")[0], rel=1e-6) == 7406935.548022923
    with subtests.test("VarOpEx"):
        assert pytest.approx(prob.get_val("sys.VarOpEx")[0], rel=1e-6) == 9420636.00753175
    with subtests.test("Cost year"):
        assert prob.get_val("sys.cost_year") == 2024
