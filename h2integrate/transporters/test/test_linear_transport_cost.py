import pytest
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.core.sites import SiteLocationComponent
from h2integrate.transporters.linear_transport_cost import LinearDistanceCostModel


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
    cost_config = {
        "capex_per_km": 1e6,
        "fixed_opex_per_km": 1e6 * 0.05,
        "cost_year": 2022,
    }

    transport_comp = LinearDistanceCostModel(
        plant_config=plant_config,
        tech_config={"model_inputs": {"cost_parameters": cost_config}},
        driver_config={},
    )

    prob = om.Problem()

    prob.model.add_subsystem("source_site", SiteLocationComponent(source_site_config))
    prob.model.add_subsystem("dest_site", SiteLocationComponent(dest_site_config))
    prob.model.add_subsystem("transport", transport_comp)

    prob.model.connect("source_site.latitude", "transport.source_latitude")
    prob.model.connect("source_site.longitude", "transport.source_longitude")
    prob.model.connect("dest_site.latitude", "transport.dest_latitude")
    prob.model.connect("dest_site.longitude", "transport.dest_longitude")

    prob.setup()
    prob.run_model()

    with subtests.test("Distance between sites"):
        assert (
            approx(prob.model.get_val("transport.transport_distance", units="km")[0], rel=1e-6)
            == 750.7044132298796
        )

    expected_cpx = (
        prob.model.get_val("transport.transport_distance", units="km") * cost_config["capex_per_km"]
    )
    expected_opx = (
        prob.model.get_val("transport.transport_distance", units="km")
        * cost_config["fixed_opex_per_km"]
    )

    with subtests.test("Expected CapEx"):
        assert approx(prob.model.get_val("transport.CapEx", units="USD"), rel=1e-6) == expected_cpx

    with subtests.test("Expected OpEx"):
        assert (
            approx(prob.model.get_val("transport.OpEx", units="USD/yr"), rel=1e-6) == expected_opx
        )

    # Set destination site to Golden, CO
    prob.set_val("dest_site.latitude", 39.744, units="deg")
    prob.set_val("dest_site.longitude", -105.173, units="deg")
    prob.run_model()

    with subtests.test("Distance between sites (#2)"):
        assert (
            approx(prob.model.get_val("transport.transport_distance", units="km")[0], rel=1e-6)
            == 299.4637107845708
        )

    expected_cpx = (
        prob.model.get_val("transport.transport_distance", units="km") * cost_config["capex_per_km"]
    )
    expected_opx = (
        prob.model.get_val("transport.transport_distance", units="km")
        * cost_config["fixed_opex_per_km"]
    )

    with subtests.test("Expected CapEx (#2)"):
        assert approx(prob.model.get_val("transport.CapEx", units="USD"), rel=1e-6) == expected_cpx

    with subtests.test("Expected OpEx (#2)"):
        assert (
            approx(prob.model.get_val("transport.OpEx", units="USD/yr"), rel=1e-6) == expected_opx
        )
