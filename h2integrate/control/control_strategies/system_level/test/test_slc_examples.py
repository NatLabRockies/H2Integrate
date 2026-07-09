import numpy as np
import pytest

from h2integrate.core.h2integrate_model import H2IntegrateModel


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("35_system_level_control/no_battery", None)]
)
def test_slc_no_battery(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "wind_ng_demand.yaml")

    model.run()

    with subtests.test("Wind set point == rated"):
        assert np.all(
            model.prob.get_val("system_level_controller.wind_electricity_set_point", units="kW")
            == model.prob.get_val("wind.rated_electricity_production", units="kW")
        )

    with subtests.test("Natural gas plant set point"):
        remaining_demand = model.prob.get_val(
            "electrical_load_demand.electricity_demand_out", units="kW"
        ) - model.prob.get_val("wind.electricity_out", units="kW")
        ng_set_point = model.prob.get_val(
            "system_level_controller.natural_gas_plant_electricity_set_point", units="kW"
        )
        expected_ng_set_point = np.clip(
            remaining_demand,
            a_min=0.0,
            a_max=model.prob.get_val("natural_gas_plant.rated_electricity_production", units="kW")[
                0
            ],
        )
        assert np.allclose(expected_ng_set_point, ng_set_point, rtol=1e-6, atol=1e-8)

    with subtests.test("Total unmet demand"):
        assert (
            pytest.approx(0.0, rel=1e-6, abs=1e-8)
            == model.prob.get_val(
                "electrical_load_demand.unmet_electricity_demand_out", units="kW"
            ).sum()
        )

    with subtests.test("Wind LCOE"):
        assert pytest.approx(77.07060204, rel=1e-6) == model.prob.get_val(
            "finance_subgroup_renewables.LCOE_profast_lco", units="USD/(MW*h)"
        )
    with subtests.test("Natural gas LCOE"):
        assert pytest.approx(85.5774049107076, rel=1e-6) == model.prob.get_val(
            "finance_subgroup_natural_gas.LCOE", units="USD/(MW*h)"
        )
    with subtests.test("Electricity LCOE"):
        assert pytest.approx(80.79533451532551, rel=1e-6) == model.prob.get_val(
            "finance_subgroup_electricity.LCOE", units="USD/(MW*h)"
        )
    with subtests.test("Wind NPV"):
        assert pytest.approx(-38.5777102298, rel=1e-6) == model.prob.get_val(
            "finance_subgroup_renewables.NPV_electricity__profast_npv", units="MUSD"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("35_system_level_control/yes_battery", None)]
)
def test_slc_yes_battery(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "wind_ng_demand.yaml")

    model.run()

    with subtests.test("Wind set point == rated"):
        assert np.all(
            model.prob.get_val("system_level_controller.wind_electricity_set_point", units="kW")
            == model.prob.get_val("wind.rated_electricity_production", units="kW")
        )

    with subtests.test("Battery set point"):
        remaining_demand = model.prob.get_val(
            "electrical_load_demand.electricity_demand_out", units="kW"
        ) - model.prob.get_val("wind.electricity_out", units="kW")
        battery_set_point = model.prob.get_val(
            "system_level_controller.battery_electricity_set_point", units="kW"
        )
        assert np.allclose(remaining_demand, battery_set_point, rtol=1e-6, atol=1e-8)

    with subtests.test("Natural gas plant set point"):
        remaining_demand = remaining_demand - model.prob.get_val(
            "battery.electricity_out", units="kW"
        )
        ng_set_point = model.prob.get_val(
            "system_level_controller.natural_gas_plant_electricity_set_point", units="kW"
        )
        expected_ng_set_point = np.clip(
            remaining_demand,
            a_min=0.0,
            a_max=model.prob.get_val("natural_gas_plant.rated_electricity_production", units="kW")[
                0
            ],
        )
        assert np.allclose(expected_ng_set_point, ng_set_point, rtol=1e-6, atol=1e-8)

    with subtests.test("Total unmet demand"):
        assert (
            pytest.approx(0.0, rel=1e-6, abs=1e-8)
            == model.prob.get_val(
                "electrical_load_demand.unmet_electricity_demand_out", units="kW"
            ).sum()
        )

    with subtests.test("Wind LCOE"):
        assert pytest.approx(77.07060204, rel=1e-6) == model.prob.get_val(
            "finance_subgroup_renewables.LCOE_profast_lco", units="USD/(MW*h)"
        )
    with subtests.test("Natural gas LCOE"):
        assert pytest.approx(161.0833612618841, rel=1e-6) == model.prob.get_val(
            "finance_subgroup_natural_gas.LCOE", units="USD/(MW*h)"
        )
    with subtests.test("Electricity LCOE"):
        assert pytest.approx(109.02003689718997, rel=1e-6) == model.prob.get_val(
            "finance_subgroup_electricity.LCOE", units="USD/(MW*h)"
        )
    with subtests.test("Wind NPV"):
        assert pytest.approx(-38.5777102298, rel=1e-6) == model.prob.get_val(
            "finance_subgroup_renewables.NPV_electricity__profast_npv", units="MUSD"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder",
    [("35_system_level_control/profit_maximization", None)],
)
def test_slc_profit_max(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "wind_ng_demand.yaml")

    n_timesteps = 8760
    sell_price = np.zeros(n_timesteps)
    for h in range(n_timesteps):
        hour_of_day = h % 24
        if 16 <= hour_of_day < 22:
            sell_price[h] = 0.08  # peak
        else:
            sell_price[h] = 0.03  # night (cheap)

    model.setup()

    model.prob.set_val(
        "system_level_controller.commodity_sell_price",
        sell_price,
        units="USD/(kW*h)",
    )

    model.run()

    wind_out = model.prob.get_val("wind.electricity_out")

    with subtests.test("wind farm generates power"):
        assert wind_out.sum() > 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("35_system_level_control/yes_hydrogen", None)]
)
def test_slc_yes_hydrogen(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "wind_ng_demand.yaml")

    model.run()

    wind_out = model.prob.get_val("wind.electricity_out", units="kW")

    with subtests.test("wind farm generates power"):
        assert wind_out.sum() > 0

    with subtests.test("LCOH"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg"), rel=1e-6
            )
            == 14.878096642042243
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder",
    [("35_system_level_control/battery_with_controller", None)],
)
def test_slc_battery_with_controller(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "wind_ng_demand.yaml")

    model.run()

    wind_out = model.prob.get_val("wind.electricity_out", units="kW")

    with subtests.test("wind farm generates power"):
        assert wind_out.sum() > 0
    with subtests.test("natural gas not dispatched when wind+battery cover demand"):
        demand = model.prob.get_val("electrical_load_demand.electricity_demand_out", units="kW")
        battery_out = model.prob.get_val("battery.electricity_out", units="kW")
        assert np.all(battery_out[wind_out < demand] >= 0)
    with subtests.test("lcoe"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_electricity.LCOE", units="USD/(kW*h)"),
                rel=1e-6,
            )
            == 0.109020041
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder",
    [("35_system_level_control/complex_profit_max", None)],
)
def test_slc_complex_profit_max(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "complex_profit_max.yaml")

    n_timesteps = 8760
    hours_of_day = np.tile(np.arange(24), 365)
    day_of_year = np.repeat(np.arange(365), 24)

    # Non-constant demand: base 50 MW, daytime bump to ~80 MW, summer cooling peak
    base_demand = 50_000  # kW
    daytime_bump = np.where((hours_of_day >= 7) & (hours_of_day < 21), 30_000, 0)
    seasonal_demand = 1.0 + 0.4 * np.sin(2 * np.pi * (day_of_year - 172) / 365)
    demand_profile = (base_demand + daytime_bump) * seasonal_demand

    # ERCOT-like wholesale sell price ($/kWh) with diurnal shape
    sell_price = np.zeros(n_timesteps)
    for h in range(n_timesteps):
        hour = hours_of_day[h]
        day = day_of_year[h // 24] if h // 24 < 365 else day_of_year[-1]
        season = 1.0 + 0.35 * np.sin(2 * np.pi * (day - 172) / 365)

        if hour < 6:
            price = 0.025
        elif hour < 10:
            price = 0.025 + (hour - 6) * 0.008
        elif hour < 15:
            price = 0.035
        elif hour < 20:
            price = 0.035 + (hour - 15) * 0.018
        else:
            price = 0.125 - (hour - 20) * 0.025

        sell_price[h] = price * season

    # Summer evening price spikes
    for h in range(n_timesteps):
        day = day_of_year[h // 24] if h // 24 < 365 else day_of_year[-1]
        hour = hours_of_day[h]
        if 150 <= day <= 250 and 17 <= hour <= 20 and day % 5 == 0:
            sell_price[h] = max(sell_price[h], 0.20)

    # Grid buy price: wholesale + retail markup
    grid_buy_price = sell_price + 0.02

    model.setup()

    model.prob.set_val("electrical_load_demand.electricity_demand", demand_profile, units="kW")
    model.prob.set_val(
        "system_level_controller.commodity_sell_price",
        sell_price,
        units="USD/(kW*h)",
    )
    model.prob.set_val(
        "grid_buy.electricity_buy_price",
        grid_buy_price,
        units="USD/(kW*h)",
    )

    model.run()

    wind_out = model.prob.get_val("wind.electricity_out", units="kW")
    solar_out = model.prob.get_val("solar.electricity_out", units="kW")
    ng_out = model.prob.get_val("natural_gas_plant.electricity_out", units="kW")
    grid_out = model.prob.get_val("grid_buy.electricity_out", units="kW")

    with subtests.test("wind farm generates power"):
        assert wind_out.sum() > 0

    with subtests.test("solar farm generates power"):
        assert solar_out.sum() > 200 * 1e6

    with subtests.test("natural gas dispatched"):
        assert ng_out.sum() > 0

    with subtests.test("grid used when needed"):
        assert grid_out.sum() > 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("35_system_level_control/upstream_demand", None)]
)
def test_slc_upstream_demand(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "upstream_demand.yaml")

    model.run()

    wind_out = model.prob.get_val("wind.electricity_out", units="MW")

    with subtests.test("wind farm AEP"):
        assert pytest.approx(wind_out.sum(), rel=1e-6) == 278847.0832172

    with subtests.test("electrical load met"):
        assert (
            pytest.approx(
                model.prob.get_val("electrical_load_demand.electricity_out", units="MW").sum(),
                rel=1e-6,
            )
            == 223380.0
        )

    with subtests.test("SLC input demand"):
        assert (
            pytest.approx(
                model.prob.get_val("system_level_controller.electricity_demand", units="MW").sum(),
                rel=1e-6,
            )
            == 223380.0
        )

    with subtests.test("SLC wind set point"):
        assert np.all(
            model.prob.get_val("system_level_controller.wind_electricity_set_point", units="kW")
            == model.prob.get_val("wind.rated_electricity_production", units="kW")
        )

    with subtests.test("SLC natural_gas_plant set point"):
        assert np.all(
            model.prob.get_val(
                "system_level_controller.natural_gas_plant_electricity_set_point", units="kW"
            )
            <= model.prob.get_val("natural_gas_plant.rated_electricity_production", units="kW")
        )

    with subtests.test("Renewables LCOE"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_renewables.LCOE", units="USD/MW/h"), rel=1e-6
            )
            == 77.07060203912586
        )

    with subtests.test("Natural Gas LCOE"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_natural_gas.LCOE", units="USD/MW/h"), rel=1e-6
            )
            == 201.36578778849778
        )

    with subtests.test("LCOE"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_electricity.LCOE", units="USD/MW/h"), rel=1e-6
            )
            == 175.33434298082273
        )

    with subtests.test("LCOH"):
        assert (
            pytest.approx(
                model.prob.get_val("finance_subgroup_hydrogen.LCOH", units="USD/kg"), rel=1e-6
            )
            == 10.46208236258859
        )

    with subtests.test("Electrolyzer not in SLC"):
        slc_electrolyzer_output_var = "system_level_controller.electrolyzer_hydrogen_set_point"
        with pytest.raises(KeyError) as excinfo:
            # check that no hydrogen systems are in
            model.prob.get_val(slc_electrolyzer_output_var, units="kg/h")
        assert f"Variable '{slc_electrolyzer_output_var}' not found. " in str(excinfo.value)

    with subtests.test("H2 Storage not in SLC"):
        slc_h2s_output_var = "system_level_controller.h2_storage_hydrogen_set_point"
        with pytest.raises(KeyError) as excinfo:
            # check that no hydrogen systems are in
            model.prob.get_val(slc_h2s_output_var, units="kg/h")
        assert f"Variable '{slc_h2s_output_var}' not found. " in str(excinfo.value)
