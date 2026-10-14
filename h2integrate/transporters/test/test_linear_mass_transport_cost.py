import numpy as np
import pytest
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.core.sites import SiteLocationComponent
from h2integrate.transporters.generic_transporter import GenericTransporterPerformanceModel
from h2integrate.transporters.linear_mass_transport_cost import LinearMassTransportCostModel


@fixture
def plant_config():
    plant_dict = {
        "plant": {
            "plant_life": 30,
            "simulation": {"n_timesteps": 8760, "dt": 3600},
        }
    }
    return plant_dict


@pytest.mark.unit
def test_linear_distance_cost(plant_config, subtests):
    source_site_config = {
        # NE corner of CO
        "latitude": 40.998,
        "longitude": -102.051,
    }
    dest_site_config = {
        # 4-corners (SW corner of CO)
        "latitude": 36.999,
        "longitude": -109.045,
    }

    tech_parameters = {
        "cost_parameters": {
            "capex_per_mton_km": 1e3,  # USD/t-km
            "fixed_opex_per_mton_km": 1e3 * 0.05,  # USD/t-km/year
            "circuity_ratio": 1.0,
            "cost_year": 2022,
        },
        "performance_parameters": {
            "commodity_rate_units": "t/h",
        },
        "shared_parameters": {
            "commodity": "iron_ore",
        },
    }

    transport_cost = LinearMassTransportCostModel(
        plant_config=plant_config,
        tech_config={"model_inputs": tech_parameters},
        driver_config={},
    )
    transport_perf = GenericTransporterPerformanceModel(
        plant_config=plant_config,
        tech_config={"model_inputs": tech_parameters},
        driver_config={},
    )

    iron_profile = np.full(8760, 2.5)  # 2.5 t/h
    prob = om.Problem()

    prob.model.add_subsystem("source_site", SiteLocationComponent(source_site_config))
    prob.model.add_subsystem("dest_site", SiteLocationComponent(dest_site_config))

    transport_group = om.Group()

    transport_group = prob.model.add_subsystem("transport", om.Group())
    transport_group.add_subsystem("performance", transport_perf, promotes=["*"])
    transport_group.add_subsystem("cost", transport_cost, promotes=["*"])

    prob.model.connect("source_site.latitude", "transport.source_latitude")
    prob.model.connect("source_site.longitude", "transport.source_longitude")
    prob.model.connect("dest_site.latitude", "transport.dest_latitude")
    prob.model.connect("dest_site.longitude", "transport.dest_longitude")

    prob.setup()

    prob.set_val("transport.iron_ore_in", iron_profile, units="t/h")

    prob.run_model()

    with subtests.test("Distance between sites"):
        assert (
            approx(prob.model.get_val("transport.transport_distance", units="km")[0], rel=1e-6)
            == 750.7044132298796
        )

    expected_capex = iron_profile.sum() * 750.7044132298796 * 1e3
    with subtests.test("CapEx cost"):
        assert (
            approx(prob.model.get_val("transport.CapEx", units="USD")[0], rel=1e-6)
            == expected_capex
        )

    expected_opex = expected_capex * 0.05
    with subtests.test("CapEx cost"):
        assert (
            approx(prob.model.get_val("transport.OpEx", units="USD/yr")[0], rel=1e-6)
            == expected_opex
        )
