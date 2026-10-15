import numpy as np
import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.converters.data_center.data_center import (
    DataCenterCostModel,
    DataCenterPUEWUECostModel,
    DataCenterPerformanceModel,
    DataCenterPUEWUEPerformanceModel,
)


@fixture
def data_center_performance_params():
    """Data Center performance parameters."""
    tech_params = {
        "system_capacity_mw": 100,
        "compute_electrical_efficiency": 0.92,
        "cooling_load_ratio": 0.2,
        "water_use_gal_per_mwh": 1200,
        "demand_profile": 100.0,
    }
    return tech_params


@fixture
def data_center_cost_params():
    """Data Center cost parameters."""
    cost_params = {
        "capex_per_mw": 10e6,  # $/MW
        "fixed_opex_per_mw_per_year": 5.6e6,  # $/MW/year
        "variable_opex_per_mwh": 50,  # $/MWh
        "system_capacity_mw": 100,  # MW
        "cost_year": 2023,
    }
    return cost_params


@fixture
def plant_config():
    """Fixture to get plant configuration."""
    return {
        "plant": {
            "plant_life": 30,
            "simulation": {
                "n_timesteps": 8760,
                "dt": 3600,
            },
        },
    }


@pytest.mark.regression
def test_data_center_performance(plant_config, data_center_performance_params, subtests):
    """Test Data Center performance model with typical operating conditions."""
    tech_config_dict = {
        "model_inputs": {
            "performance_parameters": data_center_performance_params,
        }
    }

    system_capacity = data_center_performance_params["system_capacity_mw"]

    # Create a simple compute demand input profile (constant 100MW/h for 100 MW plant)
    compute_load_demand = np.full(8760, system_capacity)  # MW
    # MW, accounting for 92% efficiency (100 MW / 0.92) and 20% additional cooling load
    electrical_compute_load_demand = (
        compute_load_demand / data_center_performance_params["compute_electrical_efficiency"]
    )
    electricity_in = np.full(
        8760,
        (
            electrical_compute_load_demand
            + electrical_compute_load_demand * data_center_performance_params["cooling_load_ratio"]
        ),
    )
    water_in = np.full(8760, 1e6)

    prob = om.Problem()
    perf_comp = DataCenterPerformanceModel(
        plant_config=plant_config,
        tech_config=tech_config_dict,
    )

    prob.model.add_subsystem("data_center_perf", perf_comp, promotes=["*"])
    prob.setup()

    # Set the compute load demand input
    prob.set_val("compute_load_demand", compute_load_demand)
    prob.set_val("electricity_in", electricity_in)
    prob.set_val("water_in", water_in)
    prob.run_model()

    with subtests.test("Data Center Unmet Electricity Demand Output"):
        # Check that there is zero unmet electricity demand since the input is sufficient
        unmet_electricity_demand = prob.get_val("unmet_electricity_demand_out", units="MW")
        expected_output = [0.0] * plant_config["plant"]["simulation"]["n_timesteps"]
        assert pytest.approx(unmet_electricity_demand, rel=1e-6) == expected_output

    with subtests.test("Data Center Compute Load Output"):
        # Check compute load output is equal to the system capacity
        compute_load_out = prob.get_val("compute_load_out", units="MW")
        expected_output = [system_capacity] * plant_config["plant"]["simulation"]["n_timesteps"]
        assert pytest.approx(compute_load_out, rel=1e-6) == expected_output

    with subtests.test("Data Center Water usage"):
        # Check water usage
        water_consumed = prob.get_val("water_consumed", units="galUS/h")
        expected_output = (
            compute_load_demand * data_center_performance_params["water_use_gal_per_mwh"]
        )
        assert pytest.approx(water_consumed, rel=1e-6) == expected_output


@pytest.mark.unit
def test_data_center_cost(plant_config, data_center_cost_params, subtests):
    """Test Data Center cost model CapEx and OpEx calculations."""
    tech_config_dict = {"model_inputs": {"cost_parameters": data_center_cost_params}}

    prob = om.Problem()
    prob.model.add_subsystem(
        "data_center_cost",
        DataCenterCostModel(plant_config=plant_config, tech_config=tech_config_dict),
        promotes=["*"],
    )
    prob.setup()

    # Constant 80 MW compute load over 8760 h -> 700,800 MWh
    prob.set_val("compute_load_out", np.full(8760, 80.0), units="MW")
    prob.run_model()

    with subtests.test("Data Center CapEx"):
        # 10e6 $/MW * 100 MW
        assert prob.get_val("CapEx", units="USD")[0] == pytest.approx(1.0e9)

    with subtests.test("Data Center OpEx"):
        # fixed: 5.6e6 $/MW/yr * 100 MW = 5.6e8; variable: 50 $/MWh * 700,800 MWh = 3.504e7
        assert prob.get_val("OpEx", units="USD/year")[0] == pytest.approx(5.6e8 + 3.504e7)


# ---------------------------------------------------------------------------
# PUE/WUE data-center model
# ---------------------------------------------------------------------------


def _pue_wue_plant_config(n_timesteps=24, latitude=None, longitude=None):
    config = {
        "plant": {
            "plant_life": 30,
            "simulation": {"n_timesteps": n_timesteps, "dt": 3600},
        },
    }
    if latitude is not None and longitude is not None:
        config["sites"] = {"site": {"latitude": latitude, "longitude": longitude}}
    return config


def _pue_wue_perf_config(**overrides):
    params = {
        "compute_it_workload_profile": [1.0] * 24,
        "system_capacity_mw": 1.0,
        "pue": 1.4,
        "wue": 1.0,
        "cooling_configuration": 5,  # midsize water-cooled chiller
    }
    params.update(overrides)
    return {"model_inputs": {"performance_parameters": params}}


def _pue_wue_cost_config(**overrides):
    params = {
        "cost_year": 2022,
        "system_capacity_mw": 1.0,
        "capex_per_mw": 10_000_000.0,
        "fixed_opex_per_mw_per_year": 100_000.0,
        "electricity_rate": 0.05,
        "water_rate": 0.005,
    }
    params.update(overrides)
    return {"model_inputs": {"cost_parameters": params}}


def _build_pue_wue_perf(plant_config, tech_config):
    prob = om.Problem()
    prob.model.add_subsystem(
        "dc",
        DataCenterPUEWUEPerformanceModel(plant_config=plant_config, tech_config=tech_config),
        promotes=["*"],
    )
    prob.setup()
    prob.set_val("electricity_in", np.full(24, 10.0), units="MW")
    prob.set_val("water_in", np.full(24, 100.0), units="galUS/h")
    return prob


def _climate_zone_perf_config(**overrides):
    """PUE/WUE performance config that omits pue/wue in favor of climate_zone lookup."""
    params = {
        "compute_it_workload_profile": [1.0] * 24,
        "system_capacity_mw": 1.0,
        "climate_zone": "6A",
    }
    params.update(overrides)
    return {"model_inputs": {"performance_parameters": params}}


@pytest.mark.unit
class TestDataCenterPUEWUEClimateZoneLookup:
    """``determine_pue_wue_by_climate_zone`` must run when the user omits pue/wue."""

    def test_climate_zone_sets_pue_wue(self):
        """Supplying only climate_zone populates pue/wue on the config during setup."""
        plant_config = _pue_wue_plant_config()
        comp = DataCenterPUEWUEPerformanceModel(
            plant_config=plant_config,
            tech_config=_climate_zone_perf_config(cooling_configuration=5),
        )
        prob = om.Problem()
        prob.model.add_subsystem("dc", comp, promotes=["*"])
        prob.setup()
        # Case 5, 6A, efficient (5th quantile) → PUE=1.46, WUE=2.39
        assert comp.config.pue == pytest.approx(1.46)
        assert comp.config.wue == pytest.approx(2.39)
        assert comp.config.cooling_configuration == 5

    def test_climate_zone_autoselects_cooling_configuration(self):
        """Without an explicit cooling_configuration, the best case is chosen and stored."""
        plant_config = _pue_wue_plant_config()
        comp = DataCenterPUEWUEPerformanceModel(
            plant_config=plant_config,
            tech_config=_climate_zone_perf_config(),
        )
        prob = om.Problem()
        prob.model.add_subsystem("dc", comp, promotes=["*"])
        prob.setup()
        # 6A efficient, optimize_for="pue" (default), no size filter → case 12 (PUE=1.05).
        assert comp.config.cooling_configuration == 12
        assert comp.config.pue == pytest.approx(1.05)
        assert comp.config.wue == pytest.approx(1.56)

    def test_climate_zone_size_filter(self):
        """size_sqft restricts the auto-selection to the correct size category."""
        plant_config = _pue_wue_plant_config()
        comp = DataCenterPUEWUEPerformanceModel(
            plant_config=plant_config,
            tech_config=_climate_zone_perf_config(size_sqft=500.0),
        )
        prob = om.Problem()
        prob.model.add_subsystem("dc", comp, promotes=["*"])
        prob.setup()
        # 6A small (cases 8-10) efficient, optimize_for="pue" → case 9 (PUE=1.65).
        assert comp.config.cooling_configuration == 9
        assert comp.config.pue == pytest.approx(1.65)


@pytest.mark.unit
class TestDataCenterPUEWUELatLonLookup:
    """``determine_iecc_climate_zone`` is used when the user omits ``climate_zone``."""

    def _config_without_climate_zone(self):
        """PUE/WUE performance config with no pue/wue and no climate zone."""
        return {
            "model_inputs": {
                "performance_parameters": {
                    "compute_it_workload_profile": [1.0] * 24,
                    "system_capacity_mw": 1.0,
                    "cooling_configuration": 5,
                }
            }
        }

    def test_site_latlon_infers_climate_zone(self):
        """Site lat/lon in the plant config drives a climate-zone lookup."""
        # Duluth, MN → IECC climate zone 7 (no moisture-regime suffix).
        plant_config = _pue_wue_plant_config(latitude=46.7867, longitude=-92.1005)
        comp = DataCenterPUEWUEPerformanceModel(
            plant_config=plant_config,
            tech_config=self._config_without_climate_zone(),
        )
        prob = om.Problem()
        prob.model.add_subsystem("dc", comp, promotes=["*"])
        prob.setup()
        assert comp.config.climate_zone == "7"
        # Case 5, zone 7, efficient (5th quantile) → PUE=1.46, WUE=2.37
        assert comp.config.pue == pytest.approx(1.46)
        assert comp.config.wue == pytest.approx(2.37)

    def test_missing_site_raises(self):
        """Without pue/wue, climate_zone, or a site lat/lon, setup raises a clear error."""
        plant_config = _pue_wue_plant_config()  # no sites entry
        comp = DataCenterPUEWUEPerformanceModel(
            plant_config=plant_config,
            tech_config=self._config_without_climate_zone(),
        )
        prob = om.Problem()
        prob.model.add_subsystem("dc", comp, promotes=["*"])
        with pytest.raises(ValueError, match="latitude/longitude"):
            prob.setup()


@pytest.mark.unit
class TestDataCenterPUEWUEPerformance:
    def test_facility_power_and_water(self):
        """Facility power scales with PUE; water demand scales with WUE and is capped by supply."""
        plant_config = _pue_wue_plant_config()
        prob = _build_pue_wue_perf(plant_config, _pue_wue_perf_config())
        prob.run_model()

        # 1 MW IT * PUE 1.4 = 1.4 MW total facility power
        assert prob.get_val("total_facility_power", units="MW") == pytest.approx(np.full(24, 1.4))
        assert prob.get_val("compute_load_out", units="MW") == pytest.approx(np.full(24, 1.0))
        # 10 MW available electricity -> no unmet demand
        assert prob.get_val("unmet_electricity_demand", units="MW") == pytest.approx(np.zeros(24))

        # 1 MW IT * 1 h = 1000 kWh * 1.0 L/kWh = 1000 L/h = 264.2 galUS/h demand,
        # capped by the 100 galUS/h supply
        water_demand = 1000.0 / 3.785
        assert prob.get_val("water_consumed", units="galUS/h") == pytest.approx(np.full(24, 100.0))
        assert prob.get_val("unmet_water_demand", units="galUS/h") == pytest.approx(
            np.full(24, water_demand - 100.0)
        )


@pytest.mark.unit
class TestDataCenterPUEWUECost:
    def test_capex_and_opex(self):
        prob = om.Problem()
        prob.model.add_subsystem(
            "dc_cost",
            DataCenterPUEWUECostModel(
                plant_config=_pue_wue_plant_config(), tech_config=_pue_wue_cost_config()
            ),
            promotes=["*"],
        )
        prob.setup()
        prob.set_val("total_facility_power", np.full(24, 1.4), units="MW")
        prob.set_val("water_consumed", np.full(24, 100.0), units="galUS/h")
        prob.run_model()

        # capex = 10e6 $/MW * 1 MW
        assert prob.get_val("CapEx", units="USD")[0] == pytest.approx(10_000_000.0)

        # fixed_om = 100e3; electricity = 1.4 MW * 24 h * 1000 kW/MW * 0.05 = 1680;
        # water = 100 galUS/h * 24 h * 0.005 = 12
        opex = float(prob.get_val("OpEx", units="USD/year")[0])
        assert opex == pytest.approx(100_000.0 + 1_680.0 + 12.0)
