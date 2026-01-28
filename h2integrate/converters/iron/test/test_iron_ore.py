import copy
import shutil
from pathlib import Path

from pytest import approx, fixture

from h2integrate.converters.iron import iron


@fixture
def iron_ore():
    iron_ore = {
        "project_parameters": {
            "cost_year": 2022,
            "project_lifetime": 30,
            "grid_connection": False,
            "ppa_price": 0.025,
            "hybrid_electricity_estimated_cf": 0.492,
            "financial_analysis_start_year": 2032,
            "installation_time": 36,
        },
        "iron": {
            "site": {
                "lat": 47.29415278,
                "lon": -91.25649444,
                "resource_dir": "/../data_library/weather/",
                "name": "Northshore",
            },
            "product_selection": "drg_taconite_pellets",  # 'std_taconite_pellets'
            "performance_model": {
                "name": "martin_ore",
                "refit_coeffs": False,
            },
            "cost_model": {
                "name": "martin_ore",
                "refit_coeffs": False,
            },
            "finance_model": {
                "name": "martin_ore",  # 'rosner_ore' also an option
            },
            "performance": {
                "input_capacity_factor_estimate": 0.9,
            },
            "costs": {
                "operational_year": 2035,
                "installation_years": 3,
                "plant_life": 30,
                "o2_heat_integration": False,
                "lcoh": 2.80,
            },
            "finances": {
                "lcoh": 2.80,
                "gen_inflation": 0.025,
                "financial_assumptions": {
                    "total income tax rate": 0.2574,
                    "capital gains tax rate": 0.15,
                    "leverage after tax nominal discount rate": 0.10893,
                    "debt equity ratio of initial financing": 0.624788,
                    "debt interest rate": 0.050049,
                },
            },
        },
    }
    return iron_ore


def test_run_martin_iron_ore(iron_ore, subtests):
    performance, cost, finance = iron.run_iron_full_model(iron_ore)
    perf_df = performance.performances_df
    cost_df = cost.costs_df

    with subtests.test("performance model: drg_taconite_pellets"):
        assert perf_df.loc[perf_df["Name"] == "Pellet Fe Content", "Northshore"].values[
            0
        ] == approx(67.35, 1e-3)
    with subtests.test("cost model: drg_taconite_pellets"):
        assert cost_df.loc[
            cost_df["Name"] == "Buildings and other structures", "Northshore"
        ].values[0] == approx(1012588246, 1e-3)
    with subtests.test("finance model: drg_taconite_pellets"):
        # TODO: verify value - just copied result
        assert finance.sol["lco"] == approx(125.25, 1e-3)

    # Test a different ore type
    iron_ore_copy = copy.deepcopy(iron_ore)  # Create an isolated copy
    iron_ore_copy["iron"]["product_selection"] = "std_taconite_pellets"
    performance, cost, finance = iron.run_iron_full_model(iron_ore_copy)
    perf_df = performance.performances_df
    cost_df = cost.costs_df
    with subtests.test("performance model: std_taconite_pellets"):
        assert perf_df.loc[perf_df["Name"] == "Pellet Fe Content", "Northshore"].values[
            0
        ] == approx(65.0, 1e-3)
    with subtests.test("cost model: std_taconite_pellets"):
        assert cost_df.loc[
            cost_df["Name"] == "Buildings and other structures", "Northshore"
        ].values[0] == approx(802586723.3, 1e-3)
    with subtests.test("finance model: std_taconite_pellets"):
        # TODO: verify value - just copied result
        assert finance.sol["lco"] == approx(99.28, 1e-3)

    # Test a different mine location
    # TODO: check that site lat/lon get updated if you're changing site name
    iron_ore_copy = copy.deepcopy(iron_ore)  # Create an isolated copy
    iron_ore_copy["iron"]["site"]["name"] = "United"
    performance, cost, finance = iron.run_iron_full_model(iron_ore_copy)
    perf_df = performance.performances_df
    cost_df = cost.costs_df
    with subtests.test("performance model: different location"):
        assert perf_df.loc[perf_df["Name"] == "Pellet Fe Content", "United"].values[0] == approx(
            67.63, 1e-3
        )
    with subtests.test("cost model: different location"):
        assert cost_df.loc[cost_df["Name"] == "Buildings and other structures", "United"].values[
            0
        ] == approx(1118066189.0, 1e-3)
    with subtests.test("finance model: different location"):
        # TODO: verify value - just copied result
        assert finance.sol["lco"] == approx(141.91, 1e-3)


def test_refit_coefficients(iron_ore, subtests):
    # Determine the model directory based on the model name
    iron_tech_dir = (
        Path(__file__).parent.parent.parent.parent / "h2integrate" / "converters" / "iron"
    )
    model_name = iron_ore["iron"]["cost_model"]["name"]
    model_dir = iron_tech_dir / model_name

    # Backup both performance and cost coefficient files
    cost_coeffs_file = model_dir / "cost_coeffs.csv"
    cost_backup_file = model_dir / "cost_coeffs_backup.csv"
    perf_coeffs_file = model_dir / "perf_coeffs.csv"
    perf_backup_file = model_dir / "perf_coeffs_backup.csv"

    if cost_coeffs_file.exists():
        shutil.copy2(cost_coeffs_file, cost_backup_file)
    if perf_coeffs_file.exists():
        shutil.copy2(perf_coeffs_file, perf_backup_file)

    # Non-refit coefficients
    performance, cost, finance = iron.run_iron_full_model(iron_ore)
    perf_df = performance.performances_df
    cost_df = cost.costs_df

    # Refit coefficients performance model
    iron_ore_copy = copy.deepcopy(iron_ore)
    iron_ore_copy["iron"]["performance_model"]["refit_coeffs"] = True
    performance2, cost2, finance2 = iron.run_iron_full_model(iron_ore_copy)
    perf_df2 = performance2.performances_df
    cost_df2 = cost2.costs_df
    with subtests.test("performance model: refit coefficients"):
        assert perf_df2.loc[perf_df2["Name"] == "Pellet Fe Content", "Northshore"].values[
            0
        ] == approx(
            perf_df.loc[perf_df["Name"] == "Pellet Fe Content", "Northshore"].values[0], 1e-3
        )
    with subtests.test("cost model: refit coefficients"):
        assert cost_df2.loc[
            cost_df2["Name"] == "Buildings and other structures", "Northshore"
        ].values[0] == approx(
            cost_df.loc[cost_df["Name"] == "Buildings and other structures", "Northshore"].values[
                0
            ],
            1e-3,
        )
    with subtests.test("finance model: refit coefficients"):
        assert finance2.sol["lco"] == approx(finance.sol["lco"], 1e-3)

    # Refit coefficients cost model
    iron_ore_copy = copy.deepcopy(iron_ore)
    iron_ore_copy["iron"]["cost_model"]["refit_coeffs"] = True
    performance2, cost2, finance2 = iron.run_iron_full_model(iron_ore_copy)
    perf_df2 = performance2.performances_df
    cost_df2 = cost2.costs_df
    with subtests.test("performance model: refit coefficients"):
        assert perf_df2.loc[perf_df2["Name"] == "Pellet Fe Content", "Northshore"].values[
            0
        ] == approx(
            perf_df.loc[perf_df["Name"] == "Pellet Fe Content", "Northshore"].values[0], 1e-3
        )
    with subtests.test("cost model: refit coefficients"):
        assert cost_df2.loc[
            cost_df2["Name"] == "Buildings and other structures", "Northshore"
        ].values[0] == approx(
            cost_df.loc[cost_df["Name"] == "Buildings and other structures", "Northshore"].values[
                0
            ],
            1e-3,
        )
    with subtests.test("finance model: refit coefficients"):
        assert finance2.sol["lco"] == approx(finance.sol["lco"], 1e-3)

    # Restore the original coefficient files
    if cost_backup_file.exists():
        shutil.move(cost_backup_file, cost_coeffs_file)
    if perf_backup_file.exists():
        shutil.move(perf_backup_file, perf_coeffs_file)


def test_run_rosner_iron_ore(iron_ore, subtests):
    iron_ore_copy = copy.deepcopy(iron_ore)
    iron_ore_copy["iron"]["finance_model"]["name"] = "rosner_ore"
    performance, cost, finance = iron.run_iron_full_model(iron_ore_copy)
    perf_df = performance.performances_df
    cost_df = cost.costs_df
    with subtests.test("performance model: drg_taconite_pellets"):
        assert perf_df.loc[perf_df["Name"] == "Pellet Fe Content", "Northshore"].values[
            0
        ] == approx(67.35, 1e-3)
    with subtests.test("cost model: drg_taconite_pellets"):
        assert cost_df.loc[
            cost_df["Name"] == "Buildings and other structures", "Northshore"
        ].values[0] == approx(1012588246, 1e-3)
    with subtests.test("finance model: drg_taconite_pellets"):
        # TODO: verify value - just copied result
        assert finance.sol["lco"] == approx(207.66, 1e-3)
