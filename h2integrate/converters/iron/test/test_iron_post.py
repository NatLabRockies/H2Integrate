import copy
import shutil
from pathlib import Path

from pytest import approx, fixture

from h2integrate.converters.iron import iron


@fixture
def iron_post():
    iron_post = {
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
                "lat": 41,
                "lon": -84,
                "resource_dir": "/../data_library/weather/",
                "name": "Mid WI",
            },
            "product_selection": "ng_eaf",  # Alternative: 'h2_eaf'
            "performance_model": {
                "name": "rosner",
                "refit_coeffs": False,
            },
            "cost_model": {
                "name": "rosner",
                "refit_coeffs": False,
            },
            "finance_model": {
                "name": "rosner",  # Alternative: 'rosner_override'
            },
            "performance": {
                "plant_capacity_mtpy": 1000000,
                "capacity_denominator": "iron",  # Alternative: 'steel'
            },
            "costs": {
                "lcoh": 2.80,
                "lcoe": 0.050,
                "lco_iron_ore_tonne": 313,
                "operational_year": 2035,
                "installation_years": 3,
                "plant_life": 30,
                "o2_heat_integration": False,
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
    return iron_post


def test_ng_eaf(iron_post, subtests):
    performance, cost, finance = iron.run_iron_full_model(iron_post)
    perf_df = performance.performances_df
    cost_df = cost.costs_df

    with subtests.test("performance model: NG"):
        # TODO: verify conversion is correct
        assert perf_df.loc[perf_df["Name"] == "Natural Gas", "Model"].values[0] == approx(
            1.80, 1e-2
        )
    with subtests.test("performance model: H2"):
        # TODO: verify conversion is correct
        assert perf_df.loc[perf_df["Name"] == "Hydrogen", "Model"].values[0] == approx(0, 1e-3)
    with subtests.test("cost model"):
        # TODO: verify value - just copied result
        assert cost_df.loc[cost_df["Name"] == "EAF & Casting", "Mid WI"].values[0] == approx(
            175125136, 1e-3
        )
    with subtests.test("finance model"):
        # TODO: verify value - just copied result
        assert finance.sol["lco"] == approx(119.38, 1e-3)


def test_h2_eaf(iron_post, subtests):
    iron_post_copy = copy.deepcopy(iron_post)
    iron_post_copy["iron"]["product_selection"] = "h2_eaf"
    performance, cost, finance = iron.run_iron_full_model(iron_post_copy)
    perf_df = performance.performances_df
    cost_df = cost.costs_df

    with subtests.test("performance model: NG"):
        # TODO: verify conversion is correct
        assert perf_df.loc[perf_df["Name"] == "Natural Gas", "Model"].values[0] == approx(
            0.079, 1e-2
        )
    with subtests.test("performance model: H2"):
        # TODO: verify conversion is correct
        assert perf_df.loc[perf_df["Name"] == "Hydrogen", "Model"].values[0] == approx(0, 1e-2)
    with subtests.test("cost model"):
        # TODO: verify value - just copied result
        assert cost_df.loc[cost_df["Name"] == "EAF & Casting", "Mid WI"].values[0] == approx(
            177009717, 1e-3
        )
    with subtests.test("finance model"):
        # TODO: verify value - just copied result
        assert finance.sol["lco"] == approx(124.68, 1e-3)


def test_steel_capacity_denominator(iron_post, subtests):
    iron_post_copy = copy.deepcopy(iron_post)
    iron_post_copy["iron"]["performance"]["capacity_denominator"] = "steel"
    iron_post_copy["iron"]["product_selection"] = "h2_eaf"
    performance, cost, finance = iron.run_iron_full_model(iron_post_copy)
    perf_df = performance.performances_df
    cost_df = cost.costs_df

    with subtests.test("performance model: NG"):
        assert perf_df.loc[perf_df["Name"] == "Natural Gas", "Model"].values[0] == approx(
            0.0942, 1e-2
        )
    with subtests.test("performance model: H2"):
        assert perf_df.loc[perf_df["Name"] == "Hydrogen", "Model"].values[0] == approx(0, 1e-2)
    with subtests.test("cost model"):
        # TODO: verify value - just copied result
        assert cost_df.loc[cost_df["Name"] == "EAF & Casting", "Mid WI"].values[0] == approx(
            191769218, 1e-3
        )
    with subtests.test("finance model"):
        # TODO: verify value - just copied result
        assert finance.sol["lco"] == approx(138.31, 1e-3)


def test_rosner_override(iron_post, subtests):
    iron_post_copy = copy.deepcopy(iron_post)
    iron_post_copy["iron"]["finance_model"]["name"] = "rosner_override"
    performance, cost, finance = iron.run_iron_full_model(iron_post_copy)
    perf_df = performance.performances_df
    cost_df = cost.costs_df

    with subtests.test("performance model: NG"):
        assert perf_df.loc[perf_df["Name"] == "Natural Gas", "Model"].values[0] == approx(
            1.80, 1e-2
        )
    with subtests.test("performance model: H2"):
        assert perf_df.loc[perf_df["Name"] == "Hydrogen", "Model"].values[0] == approx(0, 1e-2)
    with subtests.test("cost model"):
        # TODO: verify value - just copied result
        assert cost_df.loc[cost_df["Name"] == "EAF & Casting", "Mid WI"].values[0] == approx(
            175125136, 1e-3
        )
    with subtests.test("finance model"):
        # TODO: verify value - just copied result
        assert finance.sol["lco"] == approx(119.0, 1e-3)


def test_refit_coefficients(iron_post, subtests):
    # Determine the model directory based on the model name
    iron_tech_dir = (
        Path(__file__).parent.parent.parent.parent / "h2integrate" / "converters" / "iron"
    )
    model_name = iron_post["iron"]["cost_model"]["name"]
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
    performance, cost, finance = iron.run_iron_full_model(iron_post)
    perf_df = performance.performances_df
    cost_df = cost.costs_df

    # Refit coefficients performance model
    iron_post_copy = copy.deepcopy(iron_post)
    iron_post_copy["iron"]["performance_model"]["refit_coeffs"] = True
    performance2, cost2, finance2 = iron.run_iron_full_model(iron_post_copy)
    perf_df2 = performance2.performances_df
    cost_df2 = cost2.costs_df
    with subtests.test("performance model: NG"):
        assert perf_df2.loc[perf_df2["Name"] == "Natural Gas", "Model"].values[0] == approx(
            perf_df.loc[perf_df["Name"] == "Natural Gas", "Model"].values[0], 1e-3
        )
    with subtests.test("performance model: H2"):
        assert perf_df2.loc[perf_df2["Name"] == "Hydrogen", "Model"].values[0] == approx(
            perf_df.loc[perf_df["Name"] == "Hydrogen", "Model"].values[0], 1e-3
        )
    with subtests.test("cost model"):
        assert cost_df2.loc[cost_df2["Name"] == "EAF & Casting", "Mid WI"].values[0] == approx(
            cost_df.loc[cost_df["Name"] == "EAF & Casting", "Mid WI"].values[0], 1e-3
        )
    with subtests.test("finance model"):
        assert finance.sol["lco"] == approx(finance.sol["lco"], 1e-3)

    # Refit coefficients cost model
    iron_post_copy = copy.deepcopy(iron_post)
    iron_post_copy["iron"]["cost_model"]["refit_coeffs"] = True
    performance2, cost2, finance2 = iron.run_iron_full_model(iron_post_copy)
    perf_df2 = performance2.performances_df
    cost_df2 = cost2.costs_df
    with subtests.test("performance model: NG"):
        assert perf_df2.loc[perf_df2["Name"] == "Natural Gas", "Model"].values[0] == approx(
            perf_df.loc[perf_df["Name"] == "Natural Gas", "Model"].values[0], 1e-3
        )
    with subtests.test("performance model: H2"):
        assert perf_df2.loc[perf_df2["Name"] == "Hydrogen", "Model"].values[0] == approx(
            perf_df.loc[perf_df["Name"] == "Hydrogen", "Model"].values[0], 1e-3
        )
    with subtests.test("cost model"):
        assert cost_df2.loc[cost_df2["Name"] == "EAF & Casting", "Mid WI"].values[0] == approx(
            cost_df.loc[cost_df["Name"] == "EAF & Casting", "Mid WI"].values[0], 1e-3
        )
    with subtests.test("finance model"):
        assert finance.sol["lco"] == approx(finance.sol["lco"], 1e-3)

    # Restore the original coefficient files
    if cost_backup_file.exists():
        shutil.move(cost_backup_file, cost_coeffs_file)
    if perf_backup_file.exists():
        shutil.move(perf_backup_file, perf_coeffs_file)
