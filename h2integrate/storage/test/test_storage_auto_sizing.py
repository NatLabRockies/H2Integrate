import numpy as np
import pytest
import openmdao.api as om

from h2integrate.storage.simple_storage_auto_sizing import StorageAutoSizingModel
from h2integrate.control.control_strategies.storage.simple_openloop_controller import (
    SimpleStorageOpenLoopController,
)


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_storage_autosizing_basic_performance_no_losses(plant_config, subtests):
    # Basic test to ensure that storage outputs (charge profile, discharge profile, SOC)
    # don't violate any performance constraints and that the calculated storage sizes
    # are as expected
    performance_model_config = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "set_demand_as_avg_commodity_in": True,
        "min_soc_fraction": 0.0,
        "max_soc_fraction": 1.0,
        "commodity_amount_units": "kg",
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
    }

    commodity_in = np.concat(
        [np.full(3, 12.0), np.cumsum(np.ones(15)), np.full(3, 4.0), np.zeros(3)]
    )
    commodity_demand = np.full(24, np.mean(commodity_in))

    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(
            name="hydrogen_set_point", val=commodity_demand - commodity_in, units="kg/h"
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StorageAutoSizingModel(
            plant_config=plant_config,
            tech_config={"model_inputs": {"performance_parameters": performance_model_config}},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate value"):
        assert pytest.approx(charge_rate, rel=1e-6) == np.max(commodity_in)

    with subtests.test("Storage capacity value"):
        soc_kg = np.cumsum(commodity_demand - commodity_in)
        soc_kg_adj = soc_kg + np.abs(np.min(soc_kg))
        expected_capacity = np.max(soc_kg_adj) - np.min(soc_kg_adj)
        assert pytest.approx(capacity, rel=1e-6) == expected_capacity

    with subtests.test("Storage duration"):
        expected_storage_duration = expected_capacity / np.max(commodity_in)
        assert (
            pytest.approx(prob.get_val("storage_duration", units="h"), rel=1e-6)
            == expected_storage_duration
        )

    # Basic sanity-check unit tests on storage performance
    with subtests.test("Discharge is always positive"):
        assert np.all(prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") >= 0)

    with subtests.test("Charge is always negative"):
        assert np.all(prob.get_val("storage.storage_hydrogen_charge", units="kg/h") <= 0)

    with subtests.test("Charge + Discharge == storage_hydrogen_out"):
        charge_plus_discharge = prob.get_val(
            "storage.storage_hydrogen_charge", units="kg/h"
        ) + prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")
        np.testing.assert_allclose(
            charge_plus_discharge, prob.get_val("storage_hydrogen_out", units="kg/h"), rtol=1e-6
        )

    # Check that never charging and discharging at the same time
    indx_soc_increase = np.argwhere(
        np.diff(prob.model.get_val("storage.SOC", units="unitless"), prepend=True) > 0
    ).flatten()
    indx_soc_decrease = np.argwhere(
        np.diff(prob.model.get_val("storage.SOC", units="unitless"), prepend=False) < 0
    ).flatten()
    indx_soc_same = np.argwhere(
        np.diff(prob.model.get_val("storage.SOC", units="unitless"), prepend=True) == 0.0
    ).flatten()

    with subtests.test("SOC increases when charging"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[indx_soc_increase] < 0
        )
        assert np.all(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[indx_soc_decrease] == 0
        )
        assert np.all(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[indx_soc_same] == 0
        )

    with subtests.test("SOC decreases when discharging"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_decrease] > 0
        )
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_increase] == 0
        )
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")[indx_soc_same] == 0
        )

    # Check that charge rate limits are respected
    with subtests.test("Charge never exceeds charge rate"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h") >= -1 * charge_rate
        )

    with subtests.test("Discharge never exceeds discharge rate"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") <= charge_rate
        )

    with subtests.test("Discharge never exceeds demand"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h") <= commodity_demand
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert np.cumsum(prob.get_val("storage_hydrogen_out", units="kg/h")).max() <= capacity
        assert np.cumsum(prob.get_val("storage_hydrogen_out", units="kg/h")).min() >= -1 * capacity

    # Check that demand is fully met, this is because this test starts off with charging the storage
    # enough. In cases where the storage is not charged enough at the start, the demand may not
    # fully be met
    with subtests.test("Demand is fully met"):
        np.testing.assert_allclose(
            prob.get_val("hydrogen_out", units="kg/h"), commodity_demand, rtol=1e-6, atol=1e-10
        )

    with subtests.test("Unmet demand"):
        np.testing.assert_allclose(
            prob.get_val("unmet_hydrogen_demand_out", units="kg/h"),
            np.zeros(len(commodity_demand)),
            rtol=1e-6,
            atol=1e-10,
        )

    with subtests.test("Discharge Profile"):
        expected_discharge = np.concat(
            [np.zeros(3), np.arange(6, 0, -1), np.zeros(9), np.full(3, 3.0), np.full(3, 7.0)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
            atol=1e-10,
        )

    with subtests.test("Charge Profile"):
        expected_charge = np.concat(
            [np.full(3, -5), np.zeros(7), np.arange(-1, -8, -1), np.array([-3]), np.zeros(6)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
            atol=1e-10,
        )

    with subtests.test("Total unused commodity"):
        assert (
            pytest.approx(prob.get_val("unused_hydrogen_out", units="kg/h").sum(), rel=1e-6) == 5.0
        )


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_storage_autosizing_soc_bounds(plant_config, subtests):
    performance_model_config = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "set_demand_as_avg_commodity_in": True,
        "min_soc_fraction": 0.1,
        "max_soc_fraction": 0.9,
        "commodity_amount_units": "kg",
        "charge_efficiency": 1.0,
        "discharge_efficiency": 1.0,
    }

    commodity_in = np.concat(
        [np.full(3, 12.0), np.cumsum(np.ones(15)), np.full(3, 4.0), np.zeros(3)]
    )
    commodity_demand = np.full(24, np.mean(commodity_in))

    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(
            name="hydrogen_set_point", val=commodity_demand - commodity_in, units="kg/h"
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StorageAutoSizingModel(
            plant_config=plant_config,
            tech_config={"model_inputs": {"performance_parameters": performance_model_config}},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate value"):
        assert pytest.approx(charge_rate, rel=1e-6) == np.max(commodity_in)

    with subtests.test("Storage capacity value"):
        soc_kg = np.cumsum(commodity_demand - commodity_in)
        soc_kg_adj = soc_kg + np.abs(np.min(soc_kg))
        expected_usable_capacity = np.max(soc_kg_adj) - np.min(soc_kg_adj)

        expected_capacity = expected_usable_capacity / (
            performance_model_config["max_soc_fraction"]
            - performance_model_config["min_soc_fraction"]
        )
        assert pytest.approx(capacity, rel=1e-6) == expected_capacity

    with subtests.test("Storage duration"):
        expected_storage_duration = expected_capacity / np.max(commodity_in)
        assert (
            pytest.approx(prob.get_val("storage_duration", units="h"), rel=1e-6)
            == expected_storage_duration
        )

    with subtests.test("SOC >= min SOC fraction"):
        assert np.all(
            prob.get_val("storage.SOC", units="unitless")
            >= performance_model_config["min_soc_fraction"]
        )

    with subtests.test("SOC <= max SOC fraction"):
        assert np.all(
            prob.get_val("storage.SOC", units="unitless")
            <= performance_model_config["max_soc_fraction"]
        )

    with subtests.test("Cumulative charge/discharge does not exceed storage capacity"):
        assert np.cumsum(prob.get_val("storage_hydrogen_out", units="kg/h")).max() <= capacity
        assert np.cumsum(prob.get_val("storage_hydrogen_out", units="kg/h")).min() >= -1 * capacity

    # Check that demand is fully met, this is because this test starts off with charging the storage
    # enough. In cases where the storage is not charged enough at the start, the demand may not
    # fully be met
    with subtests.test("Demand is fully met"):
        np.testing.assert_allclose(
            prob.get_val("hydrogen_out", units="kg/h"), commodity_demand, rtol=1e-6, atol=1e-10
        )


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_storage_autosizing_losses(plant_config, subtests):
    charge_eff = 0.80
    discharge_eff = 0.75
    performance_model_config = {
        "commodity": "hydrogen",
        "commodity_rate_units": "kg/h",
        "set_demand_as_avg_commodity_in": True,
        "min_soc_fraction": 0.0,
        "max_soc_fraction": 1.0,
        "commodity_amount_units": "kg",
        "charge_efficiency": charge_eff,
        "discharge_efficiency": discharge_eff,
    }

    commodity_in = np.concat(
        [np.full(3, 12.0), np.cumsum(np.ones(15)), np.full(3, 4.0), np.zeros(3)]
    )
    commodity_demand = np.full(24, np.mean(commodity_in))

    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        name="IVC2",
        subsys=om.IndepVarComp(
            name="hydrogen_set_point", val=commodity_demand - commodity_in, units="kg/h"
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StorageAutoSizingModel(
            plant_config=plant_config,
            tech_config={"model_inputs": {"performance_parameters": performance_model_config}},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Discharge never exceeds discharge rate"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_discharge", units="kg/h")
            <= charge_rate * discharge_eff
        )

    with subtests.test("Charge never exceeds charge rate"):
        assert np.all(
            prob.get_val("storage.storage_hydrogen_charge", units="kg/h")
            >= -1 * charge_rate / charge_eff
        )

    # When charging, the increase in the SOC (in kg) should be less than the commodity taken
    # from the available commodity to charge
    indx_soc_increase = np.argwhere(
        np.diff(prob.model.get_val("storage.SOC", units="unitless"), prepend=True) > 0
    ).flatten()
    soc_kg = prob.model.get_val("storage.SOC", units="unitless") * capacity
    commodity_to_soc_when_charging = np.diff(soc_kg, prepend=True)[indx_soc_increase]
    commodity_from_instream_when_charging = (
        -1 * prob.get_val("storage.storage_hydrogen_charge", units="kg/h")[indx_soc_increase]
    )
    charge_losses = 1 - (commodity_to_soc_when_charging / commodity_from_instream_when_charging)

    with subtests.test(
        "Charge efficiency: commodity from available > commodity to storage when charging"
    ):
        assert np.allclose(charge_losses, 1 - charge_eff, rtol=1e-6, atol=1e-10)

    # When discharging, the decrease in the SOC (in kg) should be more than the commodity added
    # to the available commodity from discharging
    indx_soc_decrease = np.argwhere(
        np.diff(prob.model.get_val("storage.SOC", units="unitless"), prepend=False) < 0
    ).flatten()
    commodity_from_soc_when_discharging = -1 * np.diff(soc_kg, prepend=False)[indx_soc_decrease]
    commodity_to_outstream_when_discharging = prob.get_val(
        "storage.storage_hydrogen_discharge", units="kg/h"
    )[indx_soc_decrease]
    discharge_losses = 1 - (
        commodity_to_outstream_when_discharging / commodity_from_soc_when_discharging
    )

    with subtests.test(
        "Discharge efficiency: commodity to available < commodity from storage when discharging"
    ):
        assert np.allclose(discharge_losses, 1 - discharge_eff, rtol=1e-6, atol=1e-10)

    with subtests.test("Charge Profile"):
        expected_charge = np.concat(
            [np.full(3, -5), np.zeros(7), np.arange(-1, -9, -1), np.zeros(6)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
            atol=1e-10,
        )

    with subtests.test("Discharge Profile"):
        expected_discharge = np.concat(
            [
                np.zeros(3),
                np.arange(6, 3, -1),
                np.array([2.25]),
                np.zeros(11),
                np.full(3, 3.0),
                np.array([7, 5.6, 0.0]),
            ]
        )
        np.testing.assert_allclose(
            prob.get_val("storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
            atol=1e-10,
        )


@pytest.mark.regression
@pytest.mark.parametrize("n_timesteps", [24])
def test_storage_autosizing_with_passthrough_controller(plant_config, subtests):
    # Basic test to ensure that storage performance model
    # works as-expected with the SimpleStorageOpenLoopController.
    # This test should have the same results as test_storage_autosizing_basic_performance_no_losses

    tech_config = {
        "shared_parameters": {
            "commodity": "hydrogen",
            "commodity_rate_units": "kg/h",
            "set_demand_as_avg_commodity_in": True,
        },
        "performance_parameters": {
            "min_soc_fraction": 0.0,
            "max_soc_fraction": 1.0,
            "commodity_amount_units": "kg",
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
        },
    }

    commodity_in = np.concat(
        [np.full(3, 12.0), np.cumsum(np.ones(15)), np.full(3, 4.0), np.zeros(3)]
    )
    commodity_demand = np.full(24, np.mean(commodity_in))

    prob = om.Problem()

    prob.model.add_subsystem(
        name="IVC1",
        subsys=om.IndepVarComp(name="hydrogen_in", val=commodity_in, units="kg/h"),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "controller",
        SimpleStorageOpenLoopController(
            plant_config=plant_config,
            tech_config={"model_inputs": tech_config},
        ),
        promotes=["*"],
    )

    prob.model.add_subsystem(
        "storage",
        StorageAutoSizingModel(
            plant_config=plant_config,
            tech_config={"model_inputs": tech_config},
        ),
        promotes=["*"],
    )

    prob.setup()

    prob.run_model()

    charge_rate = prob.get_val("storage.max_charge_rate", units="kg/h")[0]
    capacity = prob.get_val("storage.storage_capacity", units="kg")[0]

    with subtests.test("Charge rate value"):
        assert pytest.approx(charge_rate, rel=1e-6) == np.max(commodity_in)

    with subtests.test("Storage capacity value"):
        soc_kg = np.cumsum(commodity_demand - commodity_in)
        soc_kg_adj = soc_kg + np.abs(np.min(soc_kg))
        expected_capacity = np.max(soc_kg_adj) - np.min(soc_kg_adj)
        assert pytest.approx(capacity, rel=1e-6) == expected_capacity

    with subtests.test("Discharge Profile"):
        expected_discharge = np.concat(
            [np.zeros(3), np.arange(6, 0, -1), np.zeros(9), np.full(3, 3.0), np.full(3, 7.0)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage_hydrogen_discharge", units="kg/h"),
            expected_discharge,
            rtol=1e-6,
            atol=1e-10,
        )

    with subtests.test("Charge Profile"):
        expected_charge = np.concat(
            [np.full(3, -5), np.zeros(7), np.arange(-1, -8, -1), np.array([-3]), np.zeros(6)]
        )
        np.testing.assert_allclose(
            prob.get_val("storage_hydrogen_charge", units="kg/h"),
            expected_charge,
            rtol=1e-6,
            atol=1e-10,
        )
