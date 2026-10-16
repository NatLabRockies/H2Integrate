import yaml
import numpy as np
import pytest

from h2integrate import EXAMPLE_DIR
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
            "electrical_load_demand.electricity_demand", units="kW"
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
            "electrical_load_demand.electricity_demand", units="kW"
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
            == 9.137956305329464
        )

    with subtests.test("hydrogen demand propagates to firm electricity backup"):
        gas_set_point = model.prob.get_val(
            "system_level_controller.natural_gas_plant_electricity_set_point", units="kW"
        )
        assert np.any(gas_set_point > 1.0)
        demand = model.prob.get_val("h2_load_demand.hydrogen_demand", units="kg/h")
        np.testing.assert_allclose(
            model.prob.get_val(
                "system_level_controller.electrolyzer_hydrogen_set_point", units="kg/h"
            ),
            demand,
        )
        np.testing.assert_allclose(
            model.prob.get_val("h2_combiner.hydrogen_out", units="kg/h"), demand, rtol=1e-6
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
        demand = model.prob.get_val("electrical_load_demand.electricity_demand", units="kW")
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

    with subtests.test("grid not dispatched when always unprofitable"):
        # grid_buy_price = sell_price + 0.02 everywhere, so grid is never
        # profitable to buy under ProfitMaximizationControl. After the
        # buy_price input-to-input connection fix, the SLC sees the actual
        # per-timestep buy price (not the constant default from the tech
        # config), so the merit-order check correctly skips grid.
        assert grid_out.sum() == 0


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


@pytest.mark.integration
@pytest.mark.parametrize(
    "example_folder,resource_example_folder",
    [("35_system_level_control/heterogeneous_commodity", None)],
)
def test_slc_heterogeneous_commodity(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "heterogeneous_commodity.yaml")

    model.run()
    set_point_names = [
        name
        for name in model.prob.model.plant.system_level_controller._var_rel2meta
        if name.endswith("_set_point")
    ]
    baseline_set_point_sums = {
        name: np.asarray(model.prob.get_val(f"system_level_controller.{name}")).sum()
        for name in set_point_names
    }
    baseline_ammonia_production = np.asarray(model.prob.get_val("haber_bosch.ammonia_out")).sum()
    baseline_lcoa = np.asarray(
        model.prob.get_val("finance_subgroup_ammonia.LCOA", units="USD/kg")
    ).reshape(-1)[0]

    with subtests.test("Ammonia set point follows demand"):
        assert np.all(
            model.prob.get_val(
                "system_level_controller.haber_bosch_ammonia_set_point", units="kg/h"
            )
            == model.prob.get_val("ammonia_load_demand.ammonia_demand", units="kg/h")
        )

    with subtests.test("Hydrogen demand propagated from ammonia"):
        # The converter's ammonia set point drives a nonzero electrolyzer hydrogen set point.
        assert (
            model.prob.get_val(
                "system_level_controller.electrolyzer_hydrogen_set_point", units="kg/h"
            ).sum()
            > 0.0
        )

    with subtests.test("Electricity demand propagated to wind, solar, and battery"):
        # Hydrogen demand across the electrolyzer propagates to an electricity demand, so the
        # electricity producers appear in the controller as set-point outputs.
        assert (
            model.prob.get_val(
                "system_level_controller.wind_electricity_set_point", units="kW"
            ).sum()
            > 0.0
        )
        assert (
            model.prob.get_val(
                "system_level_controller.solar_electricity_set_point", units="kW"
            ).sum()
            > 0.0
        )
        assert (
            model.prob.get_val(
                "system_level_controller.battery_electricity_set_point", units="kW"
            ).size
            > 0
        )

    with subtests.test("Ammonia production does not exceed demand"):
        assert (
            model.prob.get_val("haber_bosch.ammonia_out", units="kg/h").sum()
            <= model.prob.get_val("ammonia_load_demand.ammonia_demand", units="kg/h").sum() + 1e-6
        )

    with subtests.test("Ammonia annual production"):
        # Below the 4000 kg/h * 8760 h ceiling: with no grid backup, wind, solar, and the
        # battery meet the ammonia demand in most but not all hours, so production falls short
        # of the full-year ceiling. Value is the true converged fixed point reached with Aitken
        # relaxation on the Gauss-Seidel dispatch loop.
        assert (
            pytest.approx(26332404.59092386, rel=1e-5)
            == model.prob.get_val("haber_bosch.ammonia_out", units="kg/h").sum()
        )

    with subtests.test("Electrolyzer hydrogen set point total"):
        assert (
            pytest.approx(7184825.71631848, rel=1e-5)
            == model.prob.get_val(
                "system_level_controller.electrolyzer_hydrogen_set_point", units="kg/h"
            ).sum()
        )

    with subtests.test("LCOA"):
        assert pytest.approx(3.39502411, rel=1e-5) == model.prob.get_val(
            "finance_subgroup_ammonia.LCOA", units="USD/kg"
        )

    plant_config_path = example_folder / "plant_config.yaml"
    with plant_config_path.open(encoding="utf-8") as config_file:
        plant_config = yaml.safe_load(config_file)
    connections = plant_config["technology_interconnections"]
    priority_connections = [edge for edge in connections if edge[0] == "electricity_splitter"]
    assert len(priority_connections) == 2
    reversed_connections = list(reversed(connections))
    splitter_positions = [
        index
        for index, edge in enumerate(reversed_connections)
        if edge[0] == "electricity_splitter"
    ]
    for position, edge in zip(splitter_positions, priority_connections, strict=True):
        reversed_connections[position] = edge
    plant_config["technology_interconnections"] = reversed_connections
    with plant_config_path.open("w", encoding="utf-8") as config_file:
        yaml.safe_dump(plant_config, config_file, sort_keys=False)

    reordered_model = H2IntegrateModel(example_folder / "heterogeneous_commodity.yaml")
    reordered_model.run()
    reordered_set_point_sums = {
        name: np.asarray(reordered_model.prob.get_val(f"system_level_controller.{name}")).sum()
        for name in set_point_names
    }
    reordered_ammonia_production = np.asarray(
        reordered_model.prob.get_val("haber_bosch.ammonia_out")
    ).sum()
    reordered_lcoa = np.asarray(
        reordered_model.prob.get_val("finance_subgroup_ammonia.LCOA", units="USD/kg")
    ).reshape(-1)[0]

    with subtests.test("reversing connections preserves outputs and splitter priority"):
        assert reordered_set_point_sums.keys() == baseline_set_point_sums.keys()
        for name in baseline_set_point_sums:
            np.testing.assert_allclose(
                reordered_set_point_sums[name],
                baseline_set_point_sums[name],
                rtol=1e-6,
                atol=1e-8,
            )
        np.testing.assert_allclose(
            reordered_ammonia_production, baseline_ammonia_production, rtol=1e-6, atol=1e-8
        )
        np.testing.assert_allclose(reordered_lcoa, baseline_lcoa, rtol=1e-6, atol=1e-8)


@pytest.mark.integration
@pytest.mark.parametrize(
    "example_folder,resource_example_folder",
    [("35_system_level_control/heterogeneous_commodity", None)],
)
def test_slc_grid_backs_haber_bosch_only(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example
    config_path = example_folder / "heterogeneous_commodity.yaml"

    baseline_model = H2IntegrateModel(config_path)
    baseline_model.run()

    def ammonia_hours_met(model):
        demand = model.prob.get_val("ammonia_load_demand.ammonia_demand", units="kg/h")
        production = model.prob.get_val("haber_bosch.ammonia_out", units="kg/h")
        # The Aitken solver can leave a small residual below the exact demand value.
        return int(np.count_nonzero((demand > 0.0) & (production >= demand * (1.0 - 1e-2))))

    baseline_served_hours = ammonia_hours_met(baseline_model)

    plant_path = example_folder / "plant_config.yaml"
    with plant_path.open(encoding="utf-8") as config_file:
        plant_config = yaml.safe_load(config_file)
    connections = [
        edge
        for edge in plant_config["technology_interconnections"]
        if "electricity_splitter" not in edge[:2]
    ]
    connections.extend(
        [
            ["elec_combiner", "electrolyzer", "electricity", "cable"],
            ["grid", "haber_bosch", "electricity", "cable"],
        ]
    )
    plant_config["technology_interconnections"] = connections
    plant_config["system_level_control"]["control_parameters"]["cost_per_tech"] = {
        "grid": "buy_price",
        "haber_bosch": "feedstock",
    }
    finance_techs = plant_config["finance_parameters"]["finance_subgroups"]["ammonia"][
        "technologies"
    ]
    if "grid" not in finance_techs:
        finance_techs.append("grid")
    with plant_path.open("w", encoding="utf-8") as config_file:
        yaml.safe_dump(plant_config, config_file, sort_keys=False)

    tech_path = example_folder / "tech_config.yaml"
    with tech_path.open(encoding="utf-8") as config_file:
        tech_config = yaml.safe_load(config_file)
    with (EXAMPLE_DIR / "24_solar_battery_grid" / "tech_config.yaml").open(
        encoding="utf-8"
    ) as config_file:
        grid_template = yaml.safe_load(config_file)["technologies"]["grid_buy"]
    # A 5 MW limit exceeds the loop's direct load without an oversized seed at zero output.
    grid_template["model_inputs"]["shared_parameters"]["interconnection_size"] = 5000.0
    tech_config["technologies"].pop("electricity_splitter")
    tech_config["technologies"]["grid"] = grid_template
    with tech_path.open("w", encoding="utf-8") as config_file:
        yaml.safe_dump(tech_config, config_file, sort_keys=False)

    grid_model = H2IntegrateModel(config_path)
    grid_model.run()

    with subtests.test("grid connection is only on the Haber-Bosch electricity path"):
        assert ["grid", "haber_bosch", "electricity", "cable"] in connections
        assert not any(edge[0] == "grid" and edge[1] == "electrolyzer" for edge in connections)

    with subtests.test("grid set point tracks Haber-Bosch electricity consumption"):
        grid_set_point = grid_model.prob.get_val(
            "system_level_controller.grid_electricity_set_point", units="kW"
        )
        haber_bosch_consumption = grid_model.prob.get_val(
            "haber_bosch.electricity_consumed", units="kW"
        )
        haber_bosch_production = grid_model.prob.get_val("haber_bosch.ammonia_out", units="kg/h")
        haber_bosch_set_point = grid_model.prob.get_val(
            "system_level_controller.haber_bosch_ammonia_set_point", units="kg/h"
        )
        # When hydrogen-limited, demanded electricity can exceed actual loop consumption.
        unconstrained = np.isclose(haber_bosch_production, haber_bosch_set_point, rtol=1e-3)
        assert unconstrained.any()
        np.testing.assert_allclose(
            grid_set_point[unconstrained],
            haber_bosch_consumption[unconstrained],
            rtol=1e-3,
            atol=1e-2,
        )

    with subtests.test("grid dispatch cannot be routed to the electrolyzer bus"):
        assert not any(
            edge[0] == "grid" and edge[1] in {"electrolyzer", "elec_combiner"}
            for edge in connections
        )
        assert grid_set_point.sum() > 0.0

    with subtests.test("grid backup serves ammonia demand in at least as many hours"):
        grid_production = np.asarray(grid_model.prob.get_val("haber_bosch.ammonia_out"))
        grid_demand = np.asarray(grid_model.prob.get_val("ammonia_load_demand.ammonia_demand"))
        hydrogen_set_point_sum = grid_model.prob.get_val(
            "system_level_controller.electrolyzer_hydrogen_set_point"
        ).sum()
        assert ammonia_hours_met(grid_model) >= baseline_served_hours, (
            f"baseline served {baseline_served_hours} hours; grid case served "
            f"{ammonia_hours_met(grid_model)}, produced {grid_production.sum()} kg, "
            f"max production {grid_production.max()} kg/h, demand sum {grid_demand.sum()} kg, "
            f"grid set-point sum {grid_set_point.sum()} kW, electrolyzer set-point sum "
            f"{hydrogen_set_point_sum} kg/h"
        )

    set_point_sums = {
        name: np.asarray(
            grid_model.prob.get_val(f"system_level_controller.{name}", units=units)
        ).sum()
        for name, units in (
            ("grid_electricity_set_point", "kW"),
            ("electrolyzer_hydrogen_set_point", "kg/h"),
        )
    }
    expected_set_point_sums = {
        "grid_electricity_set_point": 20478447.819791533,
        "electrolyzer_hydrogen_set_point": 7082756.410321653,
    }
    with subtests.test("grid and electrolyzer set-point sums"):
        for name, expected in expected_set_point_sums.items():
            assert set_point_sums[name] == pytest.approx(expected, rel=1e-5)
