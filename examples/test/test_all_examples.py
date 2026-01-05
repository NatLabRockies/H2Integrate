import os
import importlib
from pathlib import Path

import numpy as np
import pytest
import openmdao.api as om

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel


def test_steel_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "01_onshore_steel_mn")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "01_onshore_steel_mn.yaml")

    # Run the model
    model.run()

    model.post_process()
    # Subtests for checking specific values
    with subtests.test("Check LCOH"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH_delivered")[0], rel=1e-3
            )
            == 7.4937685542
        )

    with subtests.test("Check LCOS"):
        assert pytest.approx(model.prob.get_val("steel.LCOS")[0], rel=1e-3) == 1213.87728644

    with subtests.test("Check total adjusted CapEx"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.total_capex_adjusted")[0], rel=1e-3
            )
            == 5.10869916e09
        )

    with subtests.test("Check total adjusted OpEx"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.total_opex_adjusted")[0], rel=1e-3
            )
            == 97524697.65173519
        )

    with subtests.test("Check steel CapEx"):
        assert pytest.approx(model.prob.get_val("steel.CapEx"), rel=1e-3) == 5.78060014e08

    with subtests.test("Check steel OpEx"):
        assert pytest.approx(model.prob.get_val("steel.OpEx"), rel=1e-3) == 1.0129052e08


def test_simple_ammonia_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "02_texas_ammonia")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "02_texas_ammonia.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    with subtests.test("Check HOPP CapEx"):
        assert pytest.approx(model.prob.get_val("plant.hopp.hopp.CapEx"), rel=1e-3) == 1.75469962e09

    with subtests.test("Check HOPP OpEx"):
        assert pytest.approx(model.prob.get_val("plant.hopp.hopp.OpEx"), rel=1e-3) == 32953490.4

    with subtests.test("Check electrolyzer CapEx"):
        assert pytest.approx(model.prob.get_val("electrolyzer.CapEx"), rel=1e-3) == 6.00412524e08

    with subtests.test("Check electrolyzer OpEx"):
        assert pytest.approx(model.prob.get_val("electrolyzer.OpEx"), rel=1e-3) == 14703155.39207595

    with subtests.test("Check H2 storage CapEx"):
        assert pytest.approx(model.prob.get_val("h2_storage.CapEx"), rel=1e-3) == 65336874.189441

    with subtests.test("Check H2 storage OpEx"):
        assert pytest.approx(model.prob.get_val("h2_storage.OpEx"), rel=1e-3) == 3149096.037312718

    with subtests.test("Check ammonia CapEx"):
        assert pytest.approx(model.prob.get_val("ammonia.CapEx"), rel=1e-3) == 1.0124126e08

    with subtests.test("Check ammonia OpEx"):
        assert pytest.approx(model.prob.get_val("ammonia.OpEx"), rel=1e-3) == 11178036.31197754

    with subtests.test("Check total adjusted CapEx"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.total_capex_adjusted")[0], rel=1e-3
            )
            == 2577162708.3
        )

    with subtests.test("Check total adjusted OpEx"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.total_opex_adjusted")[0], rel=1e-3
            )
            == 54034051.95
        )

    # Currently underestimated compared to the Reference Design Doc
    with subtests.test("Check LCOH"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_hydrogen.LCOH")[0], rel=1e-3)
            == 3.982
        )

    with subtests.test("Check price of hydrogen"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.price_hydrogen")[0], rel=1e-3
            )
            == 3.982
        )

    # Currently underestimated compared to the Reference Design Doc
    with subtests.test("Check LCOA"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_ammonia.LCOA")[0], rel=1e-3)
            == 1.027395
        )

    # Check that the expected output files exist
    outputs_dir = Path.cwd() / "outputs"
    assert (
        outputs_dir / "profast_output_ammonia_config.yaml"
    ).is_file(), "profast_output_ammonia.yaml not found"
    assert (
        outputs_dir / "profast_output_electricity_config.yaml"
    ).is_file(), "profast_output_electricity.yaml not found"
    assert (
        outputs_dir / "profast_output_hydrogen_config.yaml"
    ).is_file(), "profast_output_hydrogen.yaml not found"


def test_ammonia_synloop_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "12_ammonia_synloop")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "12_ammonia_synloop.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    with subtests.test("Check HOPP CapEx"):
        assert pytest.approx(model.prob.get_val("plant.hopp.hopp.CapEx"), rel=1e-6) == 1.75469962e09

    with subtests.test("Check HOPP OpEx"):
        assert pytest.approx(model.prob.get_val("plant.hopp.hopp.OpEx"), rel=1e-6) == 32953490.4

    with subtests.test("Check electrolyzer CapEx"):
        assert pytest.approx(model.prob.get_val("electrolyzer.CapEx"), rel=1e-6) == 6.00412524e08

    with subtests.test("Check electrolyzer OpEx"):
        assert pytest.approx(model.prob.get_val("electrolyzer.OpEx"), rel=1e-6) == 14703155.39207595

    with subtests.test("Check H2 storage CapEx"):
        assert pytest.approx(model.prob.get_val("h2_storage.CapEx"), rel=1e-6) == 65337437.18075897

    with subtests.test("Check H2 storage OpEx"):
        assert pytest.approx(model.prob.get_val("h2_storage.OpEx"), rel=1e-6) == 3149096.037312718

    with subtests.test("Check ammonia CapEx"):
        assert pytest.approx(model.prob.get_val("ammonia.CapEx"), rel=1e-6) == 1.15173753e09

    with subtests.test("Check ammonia OpEx"):
        assert pytest.approx(model.prob.get_val("ammonia.OpEx"), rel=1e-4) == 25712447.0

    with subtests.test("Check total adjusted CapEx"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_nh3.total_capex_adjusted")[0], rel=1e-6
            )
            == 3.7289e09
        )

    with subtests.test("Check total adjusted OpEx"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_nh3.total_opex_adjusted")[0], rel=1e-6
            )
            == 79746130.53956798
        )

    with subtests.test("Check LCOH"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_h2.LCOH")[0], rel=1e-6)
            == 3.981693202109977
        )

    with subtests.test("Check LCOA"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_nh3.LCOA")[0], rel=1e-6)
            == 1.2201640214384049
        )


def test_smr_methanol_example(subtests):
    # Change the current working directory to the SMR example's directory
    os.chdir(EXAMPLE_DIR / "03_methanol" / "smr")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "03_smr_methanol.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Check levelized cost of methanol (LCOM)
    with subtests.test("Check SMR LCOM"):
        assert pytest.approx(model.prob.get_val("methanol.LCOM"), rel=1e-6) == 0.22116813


def test_co2h_methanol_example(subtests):
    # Change the current working directory to the CO2 Hydrogenation example's directory
    os.chdir(EXAMPLE_DIR / "03_methanol" / "co2_hydrogenation")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "03_co2h_methanol.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Check levelized cost of methanol (LCOM)
    with subtests.test("Check CO2 Hydrogenation LCOM"):
        assert pytest.approx(model.prob.get_val("methanol.LCOM")[0], rel=1e-6) == 1.381162


@pytest.mark.skipif(importlib.util.find_spec("mcm") is None, reason="mcm is not installed")
def test_doc_methanol_example(subtests):
    # Change the current working directory to the CO2 Hydrogenation example's directory
    os.chdir(EXAMPLE_DIR / "03_methanol" / "co2_hydrogenation_doc")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "03_co2h_methanol.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Check levelized cost of methanol (LCOM)
    with subtests.test("Check CO2 Hydrogenation LCOM"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_default.LCOM"), rel=1e-6)
            == 2.58989518
        )


def test_wind_h2_opt_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "05_wind_h2_opt")

    # Run without optimization
    model_init = H2IntegrateModel(Path.cwd() / "wind_plant_electrolyzer0.yaml")

    # Run the model
    model_init.run()

    model_init.post_process()

    annual_h20 = model_init.prob.get_val("electrolyzer.total_hydrogen_produced", units="kg/year")[0]

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "wind_plant_electrolyzer.yaml")

    # Run the model
    model.run()

    with subtests.test("Check initial H2 production"):
        assert annual_h20 < (60500000 - 10000)

    with subtests.test("Check LCOE"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_electricity.LCOE")[0], rel=1e-3)
            == 0.059096
        )

    with subtests.test("Check electrolyzer size"):
        assert (
            pytest.approx(model.prob.get_val("electrolyzer.electrolyzer_size_mw")[0], rel=1e-3)
            == 1380.0
        )
    # Read the resulting SQL file and compare initial and final LCOH values

    sql_path = None
    for root, _dirs, files in os.walk(Path.cwd()):
        for file in files:
            if file == "wind_h2_opt.sql":
                sql_path = Path(root) / file
                break
        if sql_path:
            break
    assert (
        sql_path is not None
    ), "wind_h2_opt.sql file not found in current working directory or subdirectories."

    cr = om.CaseReader(str(sql_path))
    cases = list(cr.get_cases())
    assert len(cases) > 1, "Not enough cases recorded in SQL file."

    # Get initial and final LCOH values

    initial_lcoh = cases[0].outputs["finance_subgroup_hydrogen.LCOH"][0]
    final_lcoh = cases[-1].outputs["finance_subgroup_hydrogen.LCOH"][0]

    with subtests.test("Check LCOH changed"):
        assert final_lcoh != initial_lcoh

    with subtests.test("Check total adjusted CapEx"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.total_capex_adjusted")[0], rel=1e-3
            )
            == 2667734319.98
        )
    with subtests.test("Check total adjusted OpEx"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.total_opex_adjusted")[0], rel=1e-3
            )
            == 72718135.62
        )

    with subtests.test("Check minimum total hydrogen produced"):
        assert (
            pytest.approx(
                model.prob.get_val("electrolyzer.total_hydrogen_produced", units="kg/year")[0],
                abs=15000,
            )
            == 60500000
        )


def test_paper_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "06_custom_tech")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "wind_plant_paper.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    with subtests.test("Check LCOP"):
        assert pytest.approx(model.prob.get_val("paper_mill.LCOP"), rel=1e-3) == 51.733275


@pytest.mark.skipif(importlib.util.find_spec("mcm") is None, reason="mcm is not installed")
def test_wind_wave_doc_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "09_co2/direct_ocean_capture")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "offshore_plant_doc.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    with subtests.test("Check LCOC"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_co2.LCOC")[0], rel=1e-3)
            == 2.26955589
        )

    with subtests.test("Check LCOE"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_electricity.LCOE")[0], rel=1e-3)
            == 0.330057
        )


@pytest.mark.skipif(importlib.util.find_spec("mcm") is None, reason="mcm is not installed")
def test_splitter_wind_doc_h2_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "17_splitter_wind_doc_h2")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "offshore_plant_splitter_doc_h2.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    with subtests.test("Check LCOH"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_hydrogen.LCOH")[0], rel=1e-3)
            == 10.25515911
        )

    with subtests.test("Check LCOC"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_co2.LCOC")[0], rel=1e-3)
            == 14.19802243
        )

    with subtests.test("Check LCOE"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_electricity.LCOE")[0], rel=1e-3)
            == 0.1385128
        )


def test_hydro_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "07_run_of_river_plant")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "07_run_of_river.yaml")

    # Run the model
    model.run()

    model.post_process()

    print(model.prob.get_val("finance_subgroup_default.LCOE"))

    # Subtests for checking specific values
    with subtests.test("Check LCOE"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_default.LCOE"), rel=1e-3)
            == 0.17653979
        )


def test_hybrid_energy_plant_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "11_hybrid_energy_plant")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "wind_pv_battery.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    with subtests.test("Check LCOE"):
        assert model.prob.get_val("finance_subgroup_default.LCOE", units="USD/(MW*h)")[0] < 83.2123


def test_asu_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "13_air_separator")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "13_air_separator.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    with subtests.test("Check LCON"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_default.LCON", units="USD/kg")[0],
                abs=1e-4,
            )
            == 0.309041977334972
        )


def test_hydrogen_dispatch_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "14_wind_hydrogen_dispatch")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "inputs" / "h2i_wind_to_h2_storage.yaml")

    model.run()

    model.post_process()

    with subtests.test("Check LCOE"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_electricity.LCOE", units="USD/(MW*h)")[0],
                rel=1e-5,
            )
            == 59.0962072084844
        )

    with subtests.test("Check all h2 LCOH"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_all_hydrogen.LCOH", units="USD/kg")[0],
                rel=1e-5,
            )
            == 5.380013537850591
        )

    with subtests.test("Check dispatched h2 LCOH"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_dispatched_hydrogen.LCOH", units="USD/kg")[0],
                rel=1e-5,
            )
            == 7.573354943596408
        )


@pytest.mark.skipif(importlib.util.find_spec("mcm") is None, reason="mcm is not installed")
def test_wind_wave_oae_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "09_co2/ocean_alkalinity_enhancement")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "offshore_plant_oae.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    # Note: These are placeholder values. Update with actual values after running the test
    # when MCM package is properly installed and configured
    with subtests.test("Check LCOC"):
        assert pytest.approx(model.prob.get_val("finance_subgroup_co2.LCOC"), rel=1e-3) == 37.82

    with subtests.test("Check LCOE"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_electricity.LCOE"), rel=1e-3)
            == 0.367
        )


@pytest.mark.skipif(importlib.util.find_spec("mcm") is None, reason="mcm is not installed")
def test_wind_wave_oae_example_with_finance(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "09_co2/ocean_alkalinity_enhancement_financials")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "offshore_plant_oae.yaml")

    # Run the model
    model.run()

    model.post_process()

    # Subtests for checking specific values
    # Note: These are placeholder values. Update with actual values after running the test
    # when MCM package is properly installed and configured
    with subtests.test("Check LCOE"):
        assert (
            pytest.approx(model.prob.get_val("finance_subgroup_electricity.LCOE"), rel=1e-3)
            == 0.09180
        )

    with subtests.test("Check Carbon Credit"):
        assert pytest.approx(model.prob.get_val("oae.carbon_credit_value"), rel=1e-3) == 569.5


def test_natural_gas_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "16_natural_gas")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "natgas.yaml")

    # Run the model

    model.run()

    model.post_process()
    solar_aep = sum(model.prob.get_val("solar.electricity_out", units="kW"))
    solar_bat_out_total = sum(model.prob.get_val("battery.electricity_out", units="kW"))
    solar_curtailed_total = sum(
        model.prob.get_val("battery.electricity_unused_commodity", units="kW")
    )

    renewable_subgroup_total_electricity = model.prob.get_val(
        "finance_subgroup_renewables.electricity_sum.total_electricity_produced", units="kW*h/year"
    )[0]
    electricity_subgroup_total_electricity = model.prob.get_val(
        "finance_subgroup_electricity.electricity_sum.total_electricity_produced", units="kW*h/year"
    )[0]
    natural_gas_subgroup_total_electricity = model.prob.get_val(
        "finance_subgroup_natural_gas.electricity_sum.total_electricity_produced", units="kW*h/year"
    )[0]

    # NOTE: battery output power is not included in any of the financials

    pre_ng_missed_load = model.prob.get_val("battery.electricity_unmet_demand", units="kW")
    ng_electricity_demand = model.prob.get_val("natural_gas_plant.electricity_demand", units="kW")
    ng_electricity_production = model.prob.get_val("natural_gas_plant.electricity_out", units="kW")
    bat_init_charge = 200000.0 * 0.1  # max capacity in kW and initial charge rate percentage

    with subtests.test(
        "Check solar AEP is greater than battery output (solar oversized relative to demand"
    ):
        assert solar_aep > solar_bat_out_total

    with subtests.test(
        "Check battery outputs against battery inputs (solar oversized relative to demand"
    ):
        assert (
            pytest.approx(solar_bat_out_total + solar_curtailed_total, abs=bat_init_charge)
            == solar_aep
        )

    with subtests.test("Check solar AEP equals total electricity for renewables subgroup"):
        assert pytest.approx(solar_aep, rel=1e-6) == renewable_subgroup_total_electricity

    with subtests.test("Check natural gas AEP equals total electricity for natural_gas subgroup"):
        assert (
            pytest.approx(sum(ng_electricity_production), rel=1e-6)
            == natural_gas_subgroup_total_electricity
        )

    with subtests.test(
        "Check natural gas + solar AEP equals total electricity for electricity subgroup"
    ):
        assert (
            pytest.approx(electricity_subgroup_total_electricity, rel=1e-6)
            == sum(ng_electricity_production) + solar_aep
        )

    with subtests.test("Check missed load is natural gas plant electricity demand"):
        assert pytest.approx(ng_electricity_demand, rel=1e-6) == pre_ng_missed_load

    with subtests.test("Check natural_gas_plant electricity out equals demand"):
        assert pytest.approx(ng_electricity_demand, rel=1e-6) == ng_electricity_production

    # Subtests for checking specific values
    with subtests.test("Check Natural Gas CapEx"):
        capex = model.prob.get_val("natural_gas_plant.CapEx")[0]
        assert pytest.approx(capex, rel=1e-6) == 1e8

    with subtests.test("Check Natural Gas OpEx"):
        opex = model.prob.get_val("natural_gas_plant.OpEx")[0]
        assert pytest.approx(opex, rel=1e-6) == 2243167.24525

    with subtests.test("Check total electricity produced"):
        assert pytest.approx(natural_gas_subgroup_total_electricity, rel=1e-6) == 497266898.10354495

    with subtests.test("Check opex adjusted ng_feedstock"):
        opex_ng_feedstock = model.prob.get_val(
            "finance_subgroup_natural_gas.varopex_adjusted_ng_feedstock"
            # "finance_subgroup_natural_gas.opex_adjusted_ng_feedstock"
        )[0]
        assert pytest.approx(opex_ng_feedstock, rel=1e-6) == 15281860.770986987

    with subtests.test("Check capex adjusted natural_gas_plant"):
        capex_ng_plant = model.prob.get_val(
            "finance_subgroup_natural_gas.capex_adjusted_natural_gas_plant"
        )[0]
        assert pytest.approx(capex_ng_plant, rel=1e-6) == 97560975.60975611

    with subtests.test("Check opex adjusted natural_gas_plant"):
        opex_ng_plant = model.prob.get_val(
            "finance_subgroup_natural_gas.opex_adjusted_natural_gas_plant"
        )[0]
        assert pytest.approx(opex_ng_plant, rel=1e-6) == 2188455.8490330363

    with subtests.test("Check total adjusted CapEx for natural gas subgroup"):
        total_capex = model.prob.get_val("finance_subgroup_natural_gas.total_capex_adjusted")[0]
        assert pytest.approx(total_capex, rel=1e-6) == 97658536.58536586

    with subtests.test("Check LCOE (natural gas plant)"):
        lcoe_ng = model.prob.get_val("finance_subgroup_natural_gas.LCOE")[0]
        assert pytest.approx(lcoe_ng, rel=1e-6) == 0.05811033466

    with subtests.test("Check LCOE (renewables plant)"):
        lcoe_re = model.prob.get_val("finance_subgroup_renewables.LCOE")[0]
        assert pytest.approx(lcoe_re, rel=1e-6) == 0.07102560120

    with subtests.test("Check LCOE (renewables and natural gas plant)"):
        lcoe_tot = model.prob.get_val("finance_subgroup_electricity.LCOE")[0]
        assert pytest.approx(lcoe_tot, rel=1e-6) == 0.063997927290

    # Test feedstock-specific values
    with subtests.test("Check feedstock output"):
        ng_output = model.prob.get_val("ng_feedstock_source.natural_gas_out")
        # Should be rated capacity (100 MMBtu) for all timesteps
        assert all(ng_output == 750.0)

    with subtests.test("Check feedstock consumption"):
        ng_consumed = model.prob.get_val("ng_feedstock.natural_gas_consumed")
        # Total consumption should match what the natural gas plant uses
        expected_consumption = (
            model.prob.get_val("natural_gas_plant.electricity_out") * 7.5
        )  # Convert MWh to MMBtu using heat rate
        assert pytest.approx(ng_consumed.sum(), rel=1e-3) == expected_consumption.sum()

    with subtests.test("Check feedstock CapEx"):
        ng_capex = model.prob.get_val("ng_feedstock.CapEx")[0]
        assert pytest.approx(ng_capex, rel=1e-6) == 100000.0  # start_up_cost

    with subtests.test("Check feedstock OpEx"):
        ng_opex = model.prob.get_val("ng_feedstock.VarOpEx")[0]
        # OpEx should be annual_cost (0) + price * consumption
        ng_consumed = model.prob.get_val("ng_feedstock.natural_gas_consumed")
        expected_opex = 4.2 * ng_consumed.sum()  # price = 4.2 $/MMBtu
        assert pytest.approx(ng_opex, rel=1e-6) == expected_opex


def test_wind_solar_electrolyzer_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "15_wind_solar_electrolyzer")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "15_wind_solar_electrolyzer.yaml")
    model.run()

    solar_fpath = model.model.get_val("site.solar_resource.solar_resource_data")["filepath"]
    wind_fpath = model.model.get_val("site.wind_resource.wind_resource_data")["filepath"]

    with subtests.test("Wind resource file"):
        assert Path(wind_fpath).name == "35.2018863_-101.945027_2012_wtk_v2_60min_utc_tz.csv"

    with subtests.test("Solar resource file"):
        assert Path(solar_fpath).name == "30.6617_-101.7096_psmv3_60_2013.csv"
    model.post_process()

    wind_aep = sum(model.prob.get_val("wind.electricity_out", units="kW"))
    solar_aep = sum(model.prob.get_val("solar.electricity_out", units="kW"))
    total_aep = model.prob.get_val(
        "finance_subgroup_electricity.electricity_sum.total_electricity_produced", units="kW*h/year"
    )[0]

    with subtests.test("Check total energy production"):
        assert pytest.approx(wind_aep + solar_aep, rel=1e-6) == total_aep

    with subtests.test("Check LCOE"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_electricity.LCOE", units="USD/(MW*h)")[0],
                rel=1e-5,
            )
            == 53.9306558
        )

    with subtests.test("Check LCOH"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg")[0],
                rel=1e-5,
            )
            == 5.3277923
        )

    wind_generation = model.prob.get_val("wind.electricity_out", units="kW")
    solar_generation = model.prob.get_val("solar.electricity_out", units="kW")
    total_generation = model.prob.get_val("combiner.electricity_out", units="kW")
    total_energy_to_electrolyzer = model.prob.get_val("electrolyzer.electricity_in", units="kW")
    with subtests.test("Check combiner output"):
        assert (
            pytest.approx(wind_generation.sum() + solar_generation.sum(), rel=1e-5)
            == total_generation.sum()
        )
    with subtests.test("Check electrolyzer input power"):
        assert pytest.approx(total_generation.sum(), rel=1e-5) == total_energy_to_electrolyzer.sum()


def test_electrolyzer_om_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "10_electrolyzer_om")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "electrolyzer_om.yaml")

    model.run()

    lcoe = model.prob.get_val("finance_subgroup_electricity.LCOE", units="USD/(MW*h)")[0]
    lcoh_with_lcoh_finance = model.prob.get_val(
        "finance_subgroup_hydrogen.LCOH_lcoh_financials", units="USD/kg"
    )[0]
    lcoh_with_lcoe_finance = model.prob.get_val(
        "finance_subgroup_hydrogen.LCOH_lcoe_financials", units="USD/kg"
    )[0]
    with subtests.test("Check LCOE"):
        assert pytest.approx(lcoe, rel=1e-4) == 39.98869
    with subtests.test("Check LCOH with lcoh_financials"):
        assert pytest.approx(lcoh_with_lcoh_finance, rel=1e-4) == 13.0858012
    with subtests.test("Check LCOH with lcoe_financials"):
        assert pytest.approx(lcoh_with_lcoe_finance, rel=1e-4) == 7.9935907


def test_wombat_electrolyzer_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "08_wind_electrolyzer")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "wind_plant_electrolyzer.yaml")

    model.run()

    lcoe_with_profast_model = model.prob.get_val(
        "finance_subgroup_electricity_profast.LCOE", units="USD/(MW*h)"
    )[0]
    lcoe_with_custom_model = model.prob.get_val(
        "finance_subgroup_electricity_custom.LCOE", units="USD/(MW*h)"
    )[0]

    lcoh_with_custom_model = model.prob.get_val(
        "finance_subgroup_hydrogen.LCOH_produced_custom_model", units="USD/kg"
    )[0]
    lcoh_with_profast_model = model.prob.get_val(
        "finance_subgroup_hydrogen.LCOH_produced_profast_model", units="USD/kg"
    )[0]

    with subtests.test("Check LCOH from custom  model"):
        assert pytest.approx(lcoh_with_custom_model, rel=1e-5) == 4.19232346
    with subtests.test("Check LCOH from ProFAST model"):
        assert pytest.approx(lcoh_with_profast_model, rel=1e-5) == 5.32632237
    with subtests.test("Check LCOE from custom model"):
        assert pytest.approx(lcoe_with_custom_model, rel=1e-5) == 51.17615298
    with subtests.test("Check LCOE from ProFAST model"):
        assert pytest.approx(lcoe_with_profast_model, rel=1e-5) == 59.0962084


def test_pyomo_heuristic_dispatch_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "18_pyomo_heuristic_dispatch")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "pyomo_heuristic_dispatch.yaml")

    demand_profile = np.ones(8760) * 50.0

    # TODO: Update with demand module once it is developed
    model.setup()
    model.prob.set_val("battery.electricity_demand", demand_profile, units="MW")

    # Run the model
    model.run()

    model.post_process()

    # Test battery storage functionality
    # SOC should stay within configured bounds (10% to 90%)
    # Due to pysam simulation, bounds may not be fully respected,
    # but should not exceed the upper bound more than 4% SOC
    # and the lower bound more than 1% SOC
    soc = model.prob.get_val("battery.SOC")
    with subtests.test("Check battery SOC lower bound"):
        assert all(soc >= 9.0)
    with subtests.test("Check battery SOC upper bound"):
        assert all(soc <= 94.0)

    with subtests.test("Check wind generation out of the wind plant"):
        # Wind should generate some electricity
        wind_electricity = model.prob.get_val("wind.electricity_out")
        assert wind_electricity.sum() > 0
        # Wind electricity should match battery input (direct connection)
    with subtests.test("Check wind generation in to battery"):
        battery_electricity_in = model.prob.get_val("battery.electricity_in")
        assert wind_electricity.sum() == pytest.approx(battery_electricity_in.sum(), rel=1e-6)

    with subtests.test("Check demand satisfaction"):
        electricity_out = model.prob.get_val("battery.electricity_out", units="MW")
        # Battery output should try to meet the 50 MW constant demand
        # Average output should be close to demand when there's sufficient generation
        assert electricity_out.mean() >= 45  # MW

    # Subtest for LCOE
    with subtests.test("Check all LCOE value"):
        lcoe = model.prob.get_val("finance_subgroup_all_electricity.LCOE")[0]
        assert lcoe == pytest.approx(0.08157197567200995, rel=1e-6)

    with subtests.test("Check dispatched LCOE value"):
        lcoe = model.prob.get_val("finance_subgroup_dispatched_electricity.LCOE")[0]
        assert lcoe == pytest.approx(0.5975902853904799, rel=1e-6)

    # Subtest for total electricity produced
    with subtests.test("Check total electricity produced"):
        total_electricity = model.prob.get_val(
            name="finance_subgroup_all_electricity.electricity_sum.total_electricity_produced",
            units="MW*h/year",
        )[0]
        assert total_electricity == pytest.approx(3125443.1089529935, rel=1e-6)

    # Subtest for electricity unused_commodity
    with subtests.test("Check electricity unused commodity"):
        electricity_unused_commodity = np.linalg.norm(
            model.prob.get_val("battery.unused_electricity_out", units="MW")
        )
        assert electricity_unused_commodity == pytest.approx(36590.067573337095, rel=1e-6)

    # Subtest for unmet demand
    with subtests.test("Check electricity unmet demand"):
        electricity_unmet_demand = np.linalg.norm(
            model.prob.get_val("battery.unmet_electricity_demand_out", units="MW")
        )
        assert electricity_unmet_demand == pytest.approx(711.1997294551337, rel=1e-6)

    # check that error is raised when incorrect tech_name is given
    with subtests.test("Check incorrect tech_name error"):
        expected_error = (
            r"tech_name in control_parameters \(wrong_tech_name\) must match "
            r"the top-level name of the tech group \(battery\)"
        )
        with pytest.raises(ValueError, match=expected_error):
            H2IntegrateModel(Path.cwd() / "pyomo_heuristic_dispatch_error_for_testing.yaml")


def test_simple_dispatch_example(subtests):
    # Change the current working directory to the example's directory
    os.chdir(EXAMPLE_DIR / "19_simple_dispatch")

    # Create a H2Integrate model
    model = H2IntegrateModel(Path.cwd() / "wind_battery_dispatch.yaml")

    # Run the model
    model.run()

    model.post_process()

    wind_aep = sum(model.prob.get_val("wind.electricity_out", units="kW"))
    aep_for_finance = model.prob.get_val(
        "finance_subgroup_electricity.total_electricity_produced", units="kW*h/year"
    )[0]
    battery_init_energy = 30000.0 * 0.25  # max capacity in kW and initial charge rate percentage

    with subtests.test("Check electricity is not double counted"):
        assert aep_for_finance <= wind_aep + battery_init_energy

    # Test battery storage functionality
    with subtests.test("Check battery SOC bounds"):
        soc = model.prob.get_val("battery.electricity_soc")
        # SOC should stay within configured bounds (10% to 100%)
        assert all(soc >= 0.1)
        assert all(soc <= 1.0)

    with subtests.test("Check wind generation"):
        # Wind should generate some electricity
        wind_electricity = model.prob.get_val("wind.electricity_out")
        assert wind_electricity.sum() > 0
        # Wind electricity should match battery input (direct connection)
        battery_electricity_in = model.prob.get_val("battery.electricity_in")
        assert pytest.approx(wind_electricity.sum(), rel=1e-6) == battery_electricity_in.sum()

    with subtests.test("Check demand satisfaction"):
        electricity_out = model.prob.get_val("battery.electricity_out", units="MW")
        # Battery output should try to meet the 5 MW constant demand
        # Average output should be close to demand when there's sufficient generation
        assert electricity_out.mean() > 4.20  # MW

    # Subtest for LCOE
    with subtests.test("Check LCOE value"):
        lcoe = model.prob.get_val("finance_subgroup_electricity.LCOE_all_electricity_profast")[0]
        assert pytest.approx(lcoe, rel=1e-6) == 0.07801723344476236

    # Subtest for NPV
    with subtests.test("Check NPV value"):
        npv = model.prob.get_val(
            "finance_subgroup_electricity.NPV_electricity_all_electricity_npv"
        )[0]
        assert pytest.approx(npv, rel=1e-6) == 3791194.71

    # Subtest for ProFAST NPV
    with subtests.test("Check NPV value"):
        npv = model.prob.get_val(
            "finance_subgroup_electricity.NPV_electricity_all_electricity_profast_npv"
        )[0]
        assert pytest.approx(npv, rel=1e-6) == 7518969.18

    # Subtest for total electricity produced
    with subtests.test("Check total electricity produced"):
        total_electricity = model.prob.get_val(
            "finance_subgroup_electricity.electricity_sum.total_electricity_produced"
        )[0]
        assert pytest.approx(total_electricity, rel=1e-6) == 62797265.9296355

    # Subtest for electricity unused_commodity
    with subtests.test("Check electricity unused commodity"):
        electricity_unused_commodity = np.linalg.norm(
            model.prob.get_val("battery.electricity_unused_commodity")
        )
        assert pytest.approx(electricity_unused_commodity, rel=1e-6) == 412531.73840450746

    # Subtest for unmet demand
    with subtests.test("Check electricity unmet demand"):
        electricity_unmet_demand = np.linalg.norm(
            model.prob.get_val("battery.electricity_unmet_demand")
        )
        assert pytest.approx(electricity_unmet_demand, rel=1e-6) == 165604.70758669

    # Subtest for total electricity produced from wind, should be equal to total
    # electricity produced from finance_subgroup_electricity
    with subtests.test("Check total electricity produced from wind"):
        wind_electricity_finance = model.prob.get_val(
            "finance_subgroup_wind.electricity_sum.total_electricity_produced", units="kW*h/year"
        )[0]
        assert pytest.approx(wind_electricity_finance, rel=1e-6) == total_electricity

    with subtests.test("Check total electricity produced from wind compared to wind aep"):
        wind_electricity_performance = np.sum(
            model.prob.get_val("wind.electricity_out", units="kW")
        )
        assert pytest.approx(wind_electricity_performance, rel=1e-6) == wind_electricity_finance

    # Subtest for total electricity produced from battery, should be equal
    # to sum of "battery.electricity_out"
    with subtests.test("Check total electricity produced from battery"):
        battery_electricity_finance = model.prob.get_val(
            "finance_subgroup_battery.electricity_sum.total_electricity_produced", units="MW*h/year"
        )[0]
        battery_electricity_performance = np.sum(
            model.prob.get_val("battery.electricity_out", units="MW")
        )
        assert (
            pytest.approx(battery_electricity_finance, rel=1e-6) == battery_electricity_performance
        )

    wind_lcoe = model.prob.get_val("finance_subgroup_wind.LCOE_wind_only", units="USD/(MW*h)")[0]
    battery_lcoe = model.prob.get_val(
        "finance_subgroup_battery.LCOE_battery_included", units="USD/(MW*h)"
    )[0]
    electricity_lcoe = model.prob.get_val(
        "finance_subgroup_electricity.LCOE_all_electricity_profast", units="USD/(MW*h)"
    )[0]

    with subtests.test("Check electricity LCOE is greater than wind LCOE"):
        assert electricity_lcoe > wind_lcoe

    with subtests.test("Check battery LCOE is greater than electricity LCOE"):
        assert battery_lcoe > electricity_lcoe

    with subtests.test("Check battery LCOE"):
        assert pytest.approx(battery_lcoe, rel=1e-6) == 131.781997

    with subtests.test("Check wind LCOE"):
        assert pytest.approx(wind_lcoe, rel=1e-6) == 58.8248

    with subtests.test("Check electricity LCOE"):
        assert pytest.approx(electricity_lcoe, rel=1e-6) == 78.01723


def test_csvgen_design_of_experiments(subtests):
    os.chdir(EXAMPLE_DIR / "20_solar_electrolyzer_doe")

    with pytest.raises(UserWarning) as excinfo:
        model = H2IntegrateModel(Path.cwd() / "20_solar_electrolyzer_doe.yaml")
        assert "There may be issues with the csv file csv_doe_cases.csv" in str(excinfo.value)

    import pandas as pd
    from hopp.utilities.utilities import load_yaml

    from h2integrate.core.utilities import check_file_format_for_csv_generator
    from h2integrate.core.dict_utils import update_defaults
    from h2integrate.core.inputs.validation import write_yaml, load_driver_yaml

    # load the driver config file
    driver_config = load_driver_yaml("driver_config.yaml")
    # specify the filepath to the csv file
    csv_fpath = Path(driver_config["driver"]["design_of_experiments"]["filename"]).absolute()
    # run the csv checker method, we want it to write the csv file to a new filepath so
    # set overwrite_file=False
    new_csv_filename = check_file_format_for_csv_generator(
        csv_fpath, driver_config, check_only=False, overwrite_file=False
    )

    # update the csv filename in the driver config dictionary
    updated_driver = update_defaults(driver_config["driver"], "filename", new_csv_filename.name)
    driver_config["driver"].update(updated_driver)

    # save the updated driver to a new file
    new_driver_fpath = Path.cwd() / "driver_config_test.yaml"
    new_toplevel_fpath = Path.cwd() / "20_solar_electrolyzer_doe_test.yaml"
    write_yaml(driver_config, new_driver_fpath)

    # update the driver config filename in the top-level config
    main_config = load_yaml("20_solar_electrolyzer_doe.yaml")
    main_config["driver_config"] = new_driver_fpath.name

    # save the updated top-level config file to a new file
    write_yaml(main_config, new_toplevel_fpath)

    # Run the model
    model = H2IntegrateModel(new_toplevel_fpath)
    model.run()

    # summarize sql file
    model.post_process(summarize_sql=True)

    with subtests.test("Check that sql file was summarized"):
        assert model.recorder_path is not None
        summarized_filepath = model.recorder_path.parent / f"{model.recorder_path.stem}.csv"
        assert summarized_filepath.is_file()
    with subtests.test("Check that sql summary file was written as expected"):
        summary = pd.read_csv(summarized_filepath, index_col="Unnamed: 0")
        assert len(summary) == 10
        d_var_cols = ["solar.system_capacity_DC (kW)", "electrolyzer.n_clusters (unitless)"]
        assert summary.columns.to_list()[0] in d_var_cols
        assert summary.columns.to_list()[1] in d_var_cols
        assert "finance_subgroup_hydrogen.LCOH_optimistic (USD/kg)" in summary.columns.to_list()
    # delete summary file
    summarized_filepath.unlink()

    sql_fpath = Path.cwd() / "ex_20_out" / "cases.sql"
    cr = om.CaseReader(str(sql_fpath))
    cases = list(cr.get_cases())

    with subtests.test("Check solar capacity in case 0"):
        assert (
            pytest.approx(cases[0].get_val("solar.system_capacity_DC", units="MW"), rel=1e-6)
            == 25.0
        )
    with subtests.test("Check solar capacity in case 9"):
        assert (
            pytest.approx(cases[-1].get_val("solar.system_capacity_DC", units="MW"), rel=1e-6)
            == 500.0
        )

    with subtests.test("Check electrolyzer capacity in case 0"):
        assert (
            pytest.approx(
                cases[0].get_val("electrolyzer.electrolyzer_size_mw", units="MW"), rel=1e-6
            )
            == 10.0 * 5
        )

    with subtests.test("Check electrolyzer capacity in case 9"):
        assert (
            pytest.approx(
                cases[-1].get_val("electrolyzer.electrolyzer_size_mw", units="MW"), rel=1e-6
            )
            == 10.0 * 10
        )

    min_lcoh_val = 100000.0
    min_lcoh_case_num = 0
    for i, case in enumerate(cases):
        lcoh = case.get_val("finance_subgroup_hydrogen.LCOH_optimistic", units="USD/kg")[0]
        if lcoh < min_lcoh_val:
            min_lcoh_val = np.min([lcoh, min_lcoh_val])
            min_lcoh_case_num = i

    with subtests.test("Min LCOH value"):
        assert pytest.approx(min_lcoh_val, rel=1e-6) == 4.468258

    with subtests.test("Min LCOH case number"):
        assert min_lcoh_case_num == 6

    with subtests.test("Min LCOH case LCOH value"):
        assert (
            pytest.approx(
                cases[min_lcoh_case_num].get_val(
                    "finance_subgroup_hydrogen.LCOH_optimistic", units="USD/kg"
                ),
                rel=1e-6,
            )
            == min_lcoh_val
        )

    with subtests.test("Min LCOH case has lower LCOH than other cases"):
        for i, case in enumerate(cases):
            lcoh_case = case.get_val("finance_subgroup_hydrogen.LCOH_optimistic", units="USD/kg")
            if i != min_lcoh_case_num:
                assert lcoh_case > min_lcoh_val

    with subtests.test("Min LCOH solar capacity"):
        assert (
            pytest.approx(
                cases[min_lcoh_case_num].get_val("solar.system_capacity_DC", units="MW"), rel=1e-6
            )
            == 200.0
        )

    with subtests.test("Min LCOH electrolyzer capacity"):
        assert (
            pytest.approx(
                cases[min_lcoh_case_num].get_val("electrolyzer.electrolyzer_size_mw", units="MW"),
                rel=1e-6,
            )
            == 100.0
        )

    # remove files created
    new_driver_fpath.unlink()
    new_toplevel_fpath.unlink()
    new_csv_filename.unlink()


def test_sweeping_solar_sites_doe(subtests):
    os.chdir(EXAMPLE_DIR / "22_site_doe")
    import pandas as pd

    # Create the model
    model = H2IntegrateModel("22_solar_site_doe.yaml")

    # Run the model
    model.run()

    # Specify the filepath to the sql file, the folder and filename are in the driver_config
    sql_fpath = EXAMPLE_DIR / "22_site_doe" / "ex_22_out" / "cases.sql"

    # load the cases
    cr = om.CaseReader(sql_fpath)

    cases = list(cr.get_cases())

    res_df = pd.DataFrame()
    for ci, case in enumerate(cases):
        solar_resource_data = case.get_val("site.solar_resource.solar_resource_data")
        lat_lon = f"{case.get_val('site.latitude')[0]} {case.get_val('site.longitude')[0]}"
        solar_capacity = case.get_design_vars()["solar.system_capacity_DC"]
        aep = case.get_val("solar.annual_energy", units="MW*h/yr")
        lcoe = case.get_val("finance_subgroup_electricity.LCOE_optimistic", units="USD/(MW*h)")

        site_res = pd.DataFrame(
            [aep, lcoe, solar_capacity], index=["AEP", "LCOE", "solar_capacity"], columns=[lat_lon]
        ).T
        res_df = pd.concat([site_res, res_df], axis=0)

        with subtests.test(f"Case {ci}: Solar resource latitude matches site latitude"):
            assert (
                pytest.approx(case.get_val("site.latitude"), abs=0.1)
                == solar_resource_data["site_lat"]
            )
        with subtests.test(f"Case {ci}: Solar resource longitude matches site longitude"):
            assert (
                pytest.approx(case.get_val("site.longitude"), abs=0.1)
                == solar_resource_data["site_lon"]
            )

    locations = list(set(res_df.index.to_list()))
    solar_sizes = list(set(res_df["solar_capacity"].to_list()))

    with subtests.test("Two solar sizes per site"):
        assert len(solar_sizes) == 2
    with subtests.test("Two unique sites"):
        assert len(locations) == 2

    with subtests.test("Unique AEPs per case"):
        assert len(list(set(res_df["AEP"].to_list()))) == len(res_df)

    with subtests.test("Unique LCOEs per case"):
        assert len(list(set(res_df["LCOE"].to_list()))) == len(res_df)


def test_24_solar_battery_grid_example(subtests):
    # NOTE: would be good to compare LCOE against the same example without grid selling
    # and see that LCOE reduces with grid selling
    os.chdir(EXAMPLE_DIR / "24_solar_battery_grid")

    model = H2IntegrateModel(Path.cwd() / "solar_battery_grid.yaml")

    model.run()

    model.post_process()

    energy_for_financials = model.prob.get_val(
        "finance_subgroup_renewables.electricity_sum.total_electricity_produced", units="kW*h/year"
    )

    electricity_bought = sum(model.prob.get_val("grid_buy.electricity_out", units="kW"))
    battery_missed_load = sum(model.prob.get_val("battery.electricity_unmet_demand", units="kW"))

    battery_curtailed = sum(model.prob.get_val("battery.electricity_unused_commodity", units="kW"))
    electricity_sold = sum(model.prob.get_val("grid_sell.electricity_in", units="kW"))

    solar_aep = sum(model.prob.get_val("solar.electricity_out", units="kW"))

    with subtests.test("Behavior check battery missed load is electricity bought"):
        assert pytest.approx(battery_missed_load, rel=1e-6) == electricity_bought

    with subtests.test("Behavior check battery curtailed energy is electricity sold"):
        assert pytest.approx(battery_curtailed, rel=1e-6) == electricity_sold

    with subtests.test(
        "Behavior check energy for financials; include solar aep and electricity bought"
    ):
        assert pytest.approx(energy_for_financials, rel=1e-6) == (solar_aep + electricity_bought)

    with subtests.test("Value check on LCOE"):
        lcoe = model.prob.get_val("finance_subgroup_renewables.LCOE", units="USD/(MW*h)")[0]
        assert pytest.approx(lcoe, rel=1e-4) == 91.7057887


def test_natural_geoh2(subtests):
    os.chdir(EXAMPLE_DIR / "04_geo_h2")

    h2i_nat = H2IntegrateModel(EXAMPLE_DIR / "04_geo_h2" / "04_geo_h2_natural.yaml")
    h2i_nat.run()

    with subtests.test("H2 Production"):
        assert (
            pytest.approx(
                np.mean(h2i_nat.model.get_val("geoh2_well_subsurface.hydrogen_out", units="kg/h")),
                rel=1e-6,
            )
            == 603.4286677531819
        )

    with subtests.test("integrated LCOH"):
        assert (
            pytest.approx(
                h2i_nat.prob.get_val("finance_subgroup_h2.LCOH", units="USD/kg"), rel=1e-6
            )
            == 1.59307314
        )
    with subtests.test("subsurface Capex"):
        assert (
            pytest.approx(h2i_nat.model.get_val("geoh2_well_subsurface.CapEx"), rel=1e-6)
            == 7667341.11417252
        )
    with subtests.test("subsurface fixed Opex"):
        assert (
            pytest.approx(h2i_nat.model.get_val("geoh2_well_subsurface.OpEx"), rel=1e-6)
            == 215100.7857875
        )
    with subtests.test("subsurface variable Opex"):
        assert (
            pytest.approx(h2i_nat.model.get_val("geoh2_well_subsurface.VarOpEx"), rel=1e-6) == 0.0
        )
    with subtests.test("subsurface adjusted opex"):
        adjusted_opex = h2i_nat.prob.get_val(
            "finance_subgroup_h2.opex_adjusted_geoh2_well_subsurface"
        )
        assert pytest.approx(adjusted_opex, rel=1e-6) == 215100.7857875

    with subtests.test("surface Capex"):
        assert (
            pytest.approx(h2i_nat.model.get_val("geoh2_well_surface.CapEx"), rel=1e-6) == 1795733.55
        )
    with subtests.test("surface fixed Opex"):
        assert pytest.approx(h2i_nat.model.get_val("geoh2_well_surface.OpEx"), rel=1e-6) == 4567464
    with subtests.test("surface variable Opex"):
        assert (
            pytest.approx(h2i_nat.model.get_val("geoh2_well_surface.VarOpEx"), rel=1e-6)
            == 984842.53
        )
    with subtests.test("surface adjusted opex"):
        surface_adjusted_opex = h2i_nat.prob.get_val(
            "finance_subgroup_h2.opex_adjusted_geoh2_well_surface"
        )
        assert pytest.approx(surface_adjusted_opex, rel=1e-6) == 4798691.865


def test_stimulated_geoh2(subtests):
    os.chdir(EXAMPLE_DIR / "04_geo_h2")

    h2i_stim = H2IntegrateModel(EXAMPLE_DIR / "04_geo_h2" / "04_geo_h2_stimulated.yaml")
    h2i_stim.run()

    h2_prod = h2i_stim.model.get_val("geoh2_well_subsurface.hydrogen_out", units="kg/h")

    with subtests.test("H2 Production"):
        assert pytest.approx(np.mean(h2_prod), rel=1e-6) == 155.03934945719536

    with subtests.test("integrate LCOH"):
        lcoh = h2i_stim.prob.get_val("finance_subgroup_default.LCOH")
        assert lcoh == pytest.approx(
            2.29337734, 1e-6
        )  # previous val from custom finance model was 1.74903827

    # failure is expected because we are inflating using general inflation rather than CPI and CEPCI
    with subtests.test("Capex"):
        assert (
            pytest.approx(h2i_stim.model.get_val("geoh2_well_subsurface.CapEx"), rel=1e-6)
            == 19520122.88478073
        )
    with subtests.test("fixed Opex"):
        assert (
            pytest.approx(h2i_stim.model.get_val("geoh2_well_subsurface.OpEx"), rel=1e-6)
            == 215100.7857875
        )
    with subtests.test("variable Opex"):
        var_om_pr_h2 = h2i_stim.model.get_val("geoh2_well_subsurface.VarOpEx") / np.sum(h2_prod)
        assert pytest.approx(var_om_pr_h2, rel=1e-6) == 0.32105362
    with subtests.test("adjusted Opex"):
        adjusted_opex = h2i_stim.prob.get_val(
            "finance_subgroup_default.opex_adjusted_geoh2_well_subsurface"
        )
        assert pytest.approx(adjusted_opex, rel=1e-6) == 215100.7857875


def test_21_iron_dri_eaf_example(subtests):
    os.chdir(EXAMPLE_DIR / "21_iron_mn_to_il")

    h2i = H2IntegrateModel("21_iron.yaml")

    h2i.run()

    with subtests.test("Value check on LCOI"):
        lcoi = h2i.model.get_val("finance_subgroup_iron_ore.LCOI", units="USD/t")[0]
        assert pytest.approx(lcoi, rel=1e-4) == 143.3495266638054

    with subtests.test("Value check on LCOP"):
        lcop = h2i.model.get_val("finance_subgroup_pig_iron.LCOP", units="USD/t")[0]
        assert pytest.approx(lcop, rel=1e-4) == 353.99805215243265

    with subtests.test("Value check on LCOS"):
        lcos = h2i.model.get_val("finance_subgroup_steel.LCOS", units="USD/t")[0]
        assert pytest.approx(lcos, rel=1e-4) == 524.8228189073025
