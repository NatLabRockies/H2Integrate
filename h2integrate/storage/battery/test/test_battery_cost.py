import numpy as np
import openmdao.api as om
from pytest import fixture

from h2integrate.storage.battery.atb_battery_cost import ATBBatteryCostModel
from h2integrate.control.control_strategies.storage.demand_openloop_controller import (
    DemandOpenLoopStorageController,
)


@fixture
def plant_config():
    plant_cnfg = {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
            },
        },
    }
    return plant_cnfg


@fixture
def electricity_profile_kW():
    return np.tile(np.linspace(0, 5000.0, 876), 10)


@fixture
def battery_tech_config_kW():
    battery_inputs = {
        "performance_model": {"model": "simple_generic_storage"},
        "cost_model": {"model": "atb_battery_cost"},
        "control_strategy": {"model": "demand_open_loop_storage_controller"},
        "model_inputs": {
            "shared_parameters": {
                "commodity_name": "electricity",
                "commodity_units": "kW",
                "max_charge_rate": 5000.0,
                "max_capacity": 30000.0,
            },
            "control_parameters": {
                "max_charge_percent": 1.0,
                "min_charge_percent": 0.1,
                "init_charge_percent": 0.25,
                "max_discharge_rate": 5000.0,
                "charge_efficiency": 1.0,
                "discharge_efficiency": 1.0,
                "demand_profile": 5000,
            },
            "cost_parameters": {
                "cost_year": 2022,
                "energy_capex": 391,
                "power_capex": 363,
                "opex_fraction": 0.025,
            },
        },
    }
    return battery_inputs


@fixture
def battery_tech_config_MW():
    battery_inputs = {
        "performance_model": {"model": "simple_generic_storage"},
        "cost_model": {"model": "atb_battery_cost"},
        "control_strategy": {"model": "demand_open_loop_storage_controller"},
        "model_inputs": {
            "shared_parameters": {
                "commodity_name": "electricity",
                "commodity_units": "MW",
                "max_charge_rate": 5.0,
                "max_capacity": 30.0,
            },
            "control_parameters": {
                "max_charge_percent": 1.0,
                "min_charge_percent": 0.1,
                "init_charge_percent": 0.25,
                "max_discharge_rate": 5.0,
                "charge_efficiency": 1.0,
                "discharge_efficiency": 1.0,
                "demand_profile": 5.0,
            },
            "cost_parameters": {
                "cost_year": 2022,
                "energy_capex": 391,
                "power_capex": 363,
                "opex_fraction": 0.025,
            },
        },
    }
    return battery_inputs


def test_integrated_battery_cost_kW(
    plant_config, battery_tech_config_kW, electricity_profile_kW, subtests
):
    # Set up the OpenMDAO problem
    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC",
        subsys=om.IndepVarComp(name="electricity_in", val=electricity_profile_kW),
        promotes=["*"],
    )

    controller = DemandOpenLoopStorageController(
        plant_config=plant_config, tech_config=battery_tech_config_kW
    )

    cost = ATBBatteryCostModel(plant_config=plant_config, tech_config=battery_tech_config_kW)

    prob.model.add_subsystem(
        "demand_openloop_controller",
        controller,
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "cost_model",
        cost,
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    expected_capex = ((6 * 391) + 363) * 5000.0
    expected_opex = expected_capex * 0.025

    with subtests.test("CapEx"):
        assert prob.get_val("cost_model.CapEx") == expected_capex

    with subtests.test("OpEx"):
        assert prob.get_val("cost_model.OpEx") == expected_opex


def test_integrated_battery_cost_MW(
    plant_config, battery_tech_config_MW, electricity_profile_kW, subtests
):
    # Set up the OpenMDAO problem
    prob = om.Problem()

    electricity_profile_MW = electricity_profile_kW / 1e3

    controller = DemandOpenLoopStorageController(
        plant_config=plant_config, tech_config=battery_tech_config_MW
    )

    cost = ATBBatteryCostModel(plant_config=plant_config, tech_config=battery_tech_config_MW)

    prob.model.add_subsystem(
        "demand_openloop_controller",
        controller,
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "cost_model",
        cost,
        promotes=["*"],
    )

    prob.setup()

    prob.set_val("demand_openloop_controller.electricity_in", electricity_profile_MW, units="MW")

    prob.run_model()

    expected_capex = ((6 * 391) + 363) * 5000.0
    expected_opex = expected_capex * 0.025

    with subtests.test("CapEx"):
        assert prob.get_val("cost_model.CapEx") == expected_capex

    with subtests.test("OpEx"):
        assert prob.get_val("cost_model.OpEx") == expected_opex
