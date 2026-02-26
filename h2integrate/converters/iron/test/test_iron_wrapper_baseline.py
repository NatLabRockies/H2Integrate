import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate import EXAMPLE_DIR
from h2integrate.core.inputs.validation import load_plant_yaml
from h2integrate.converters.iron.iron_wrapper import IronComponent


@fixture
def iron_config(lcoe, lcoh, site):
    iron_config = {
        "LCOE": lcoe,
        "LCOH": lcoh,
        "ROM_iron_site_name": site,
        "iron_ore_product_selection": "drg_taconite_pellets",
        "reduced_iron_site_latitude": 41.717,
        "reduced_iron_site_longitude": -88.398,
        "reduced_iron_product_selection": "ng_dri",
        "structural_iron_product_selection": "none",
        "win_capacity_denom": "iron",
        "iron_post_capacity": 1000000,
        "iron_win_capacity": 1418095,
        "ore_cf_estimate": 0.9,
        "cost_year": 2020,
    }
    return iron_config


@fixture
def location_iron_tech():
    iron_config = {
        "LCOE": 60.48,
        "LCOH": 8.86,
        "ROM_iron_site_name": "Northshore",
        "iron_ore_product_selection": "drg_taconite_pellets",
        "reduced_iron_site_latitude": 41.2,
        "reduced_iron_site_longitude": -81.7,
        "reduced_iron_product_selection": "ng_dri",
        "structural_iron_product_selection": "none",
        "win_capacity_denom": "iron",
        "iron_post_capacity": 1000000,
        "iron_win_capacity": 1418095,
        "ore_cf_estimate": 0.9,
        "cost_year": 2020,
    }
    return iron_config


@fixture
def plant_config():
    plant_config = load_plant_yaml(EXAMPLE_DIR / "21_iron_mn_to_il" / "plant_config.yaml")
    return plant_config


@pytest.mark.regression
@pytest.mark.parametrize("lcoe,lcoh,site", [(58.02, 7.1, "Northshore")])
def test_baseline_iron(plant_config, driver_config, iron_config, subtests):
    test_cases = {
        "ng/none": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "none",
        },
        "ng/eaf": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
        "h2/none": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "none",
        },
        "h2/eaf": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
    }
    expected_lcoi = {
        "ng/none": 370.212189551055,  # USD/t
        "ng/eaf": 513.8574754088993,
        "h2/none": 715.1015416039348,
        "h2/eaf": 858.9727023405763,
    }

    for test_name, test_inputs in test_cases.items():
        iron_config.update(test_inputs)
        prob = om.Problem()
        comp = IronComponent(
            plant_config=plant_config,
            tech_config={"model_inputs": {"cost_parameters": iron_config}},
            driver_config=driver_config,
        )
        prob.model.add_subsystem("iron", comp)
        prob.setup()
        prob.run_model()

        with subtests.test(f"baseline LCOI for {test_name}"):
            lcoi = prob.get_val("iron.LCOI", units="USD/t")
            assert pytest.approx(lcoi, abs=0.3) == expected_lcoi[test_name]


@pytest.mark.regression
@pytest.mark.parametrize("lcoe,lcoh,site", [(58.02, 7.1, "Hibbing")])
def test_changing_mine_iron(plant_config, driver_config, iron_config, subtests):
    test_cases = {
        "ng/none": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "none",
        },
        "ng/eaf": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
        "h2/none": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "none",
        },
        "h2/eaf": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
    }
    expected_lcoi = {
        "ng/none": 354.77730320952014,
        "ng/eaf": 498.42258906736447,
        "h2/none": 699.666052372724,
        "h2/eaf": 843.5372131093657,
    }
    for test_name, test_inputs in test_cases.items():
        iron_config.update(test_inputs)
        prob = om.Problem()
        comp = IronComponent(
            plant_config=plant_config,
            tech_config={"model_inputs": {"cost_parameters": iron_config}},
            driver_config=driver_config,
        )
        prob.model.add_subsystem("iron", comp)
        prob.setup()
        prob.run_model()

        with subtests.test(f"Hibbing mine LCOI for {test_name}"):
            lcoi = prob.get_val("iron.LCOI", units="USD/t")
            assert pytest.approx(lcoi, abs=0.3) == expected_lcoi[test_name]


@pytest.mark.regression
@pytest.mark.parametrize("lcoe,lcoh,site", [(50.0, 7.1, "Northshore")])
def test_lcoe50_iron(plant_config, driver_config, iron_config, subtests):
    test_cases = {
        "ng/none": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "none",
        },
        "ng/eaf": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
        "h2/none": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "none",
        },
        "h2/eaf": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
    }

    expected_lcoi = {
        "ng/none": 369.07934010565174,
        "ng/eaf": 509.8866655496638,
        "h2/none": 714.305073437314,
        "h2/eaf": 855.2282058088431,
    }
    for test_name, test_inputs in test_cases.items():
        iron_config.update(test_inputs)
        prob = om.Problem()
        comp = IronComponent(
            plant_config=plant_config,
            tech_config={"model_inputs": {"cost_parameters": iron_config}},
            driver_config=driver_config,
        )
        prob.model.add_subsystem("iron", comp)
        prob.setup()
        prob.run_model()

        with subtests.test(f"Hibbing mine LCOI for {test_name}"):
            lcoi = prob.get_val("iron.LCOI", units="USD/t")
            assert pytest.approx(lcoi, abs=0.3) == expected_lcoi[test_name]


@pytest.mark.regression
@pytest.mark.parametrize("lcoe,lcoh,site", [(58.02, 6.0, "Northshore")])
def test_lcoh6_iron(plant_config, driver_config, iron_config, subtests):
    test_cases = {
        "ng/none": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "none",
        },
        "ng/eaf": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
        "h2/none": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "none",
        },
        "h2/eaf": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
    }

    expected_lcoi = {
        "ng/none": 370.212189551055,
        "ng/eaf": 513.8574754088993,
        "h2/none": 653.4076529067631,
        "h2/eaf": 797.2788136434048,
    }
    for test_name, test_inputs in test_cases.items():
        iron_config.update(test_inputs)
        prob = om.Problem()
        comp = IronComponent(
            plant_config=plant_config,
            tech_config={"model_inputs": {"cost_parameters": iron_config}},
            driver_config=driver_config,
        )
        prob.model.add_subsystem("iron", comp)
        prob.setup()
        prob.run_model()

        with subtests.test(f"Hibbing mine LCOI for {test_name}"):
            lcoi = prob.get_val("iron.LCOI", units="USD/t")
            assert pytest.approx(lcoi, abs=0.3) == expected_lcoi[test_name]


@pytest.mark.regression
def test_location_iron(plant_config, driver_config, location_iron_tech, subtests):
    test_cases = {
        "ng/none": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "none",
        },
        "ng/eaf": {
            "reduced_iron_product_selection": "ng_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
        "h2/none": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "none",
        },
        "h2/eaf": {
            "reduced_iron_product_selection": "h2_dri",
            "structural_iron_product_selection": "eaf_steel",
        },
    }

    expected_lcoi = {
        "ng/none": 365.2571816,
        "ng/eaf": 509.7708257,
        "h2/none": 808.3401864,
        "h2/eaf": 953.1133839,
    }

    for test_name, test_inputs in test_cases.items():
        location_iron_tech.update(test_inputs)
        prob = om.Problem()
        comp = IronComponent(
            plant_config=plant_config,
            tech_config={"model_inputs": {"cost_parameters": location_iron_tech}},
            driver_config=driver_config,
        )
        prob.model.add_subsystem("iron", comp)
        prob.setup()
        prob.run_model()

        with subtests.test(f"Hibbing mine LCOI for {test_name}"):
            lcoi = prob.get_val("iron.LCOI", units="USD/t")
            assert pytest.approx(lcoi, abs=0.3) == expected_lcoi[test_name]
