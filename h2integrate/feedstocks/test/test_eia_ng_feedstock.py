import os
import importlib
from copy import deepcopy
from pathlib import Path

import pytest
import openmdao.api as om
from requests.exceptions import HTTPError

from h2integrate.feedstocks import FeedstockPerformanceModel
from h2integrate.feedstocks.eia_ng_price import (
    CURRENT_YEAR,
    EIANaturalGasFeedstockConfig,
    EIANaturalGasFeedstockCostModel,
)


DUMMY_KEY = "xxxxxx"
RG_NOT_INSTALLED = importlib.util.find_spec("reverse_geocoder") is None

best_trailer_in_colorado_coords = (39.9140081, -105.2249155)
definitely_not_the_us_coords = (53.5265263, -113.657807)


VALID_API_KEY_EXISTS = os.environ.get("EIA_API_KEY") is not None


@pytest.fixture
def EIA_API_key_file(temp_dir):
    """Creates a dummy EIA API key configuration file and returns the file path object."""
    good_api_fn = temp_dir / ".eiarc"
    bad_api_fn = temp_dir / ".badeiarc"
    with good_api_fn.open("w") as f:
        f.write(f"EIA_API_KEY: {DUMMY_KEY}")
    with bad_api_fn.open("w") as f:
        f.write(f"EIA_API: {DUMMY_KEY}")
    return good_api_fn, bad_api_fn


@pytest.mark.unit
def test_EIANaturalGasFeedstockConfig(subtests, EIA_API_key_file):
    """Tests a failed API for basic parameterizations."""

    good_api_fn, bad_api_fn = EIA_API_key_file

    ng_feedstock = EIANaturalGasFeedstockConfig(
        resource_year=2022,
        monthly=False,
        price_category="WELLHEAD",
        state="connecticut",
        latitude=best_trailer_in_colorado_coords[0],
        longitude=best_trailer_in_colorado_coords[1],
        cost_year=2025,
        annual_cost=1,
        start_up_cost=2,
        filename="data.csv",
        api_key_file=good_api_fn,
    )
    assert ng_feedstock.commodity == "natural_gas"
    assert ng_feedstock.commodity_rate_units == "MMBtu/h"
    assert ng_feedstock.commodity_amount_units == "MMBtu"
    assert ng_feedstock.filename == Path("./data.csv").resolve()
    assert not ng_feedstock.filename.exists()
    assert ng_feedstock.price.size == 8760
    assert ng_feedstock.price.sum() == 0
    assert ng_feedstock.resource_year == 2022
    assert not ng_feedstock.monthly
    assert ng_feedstock.price_category == "wellhead"
    assert ng_feedstock.state == "CT"
    assert ng_feedstock.latitude == best_trailer_in_colorado_coords[0]
    assert ng_feedstock.longitude == best_trailer_in_colorado_coords[1]
    assert ng_feedstock.cost_year == 2025
    assert ng_feedstock.annual_cost == 1.0
    assert ng_feedstock.start_up_cost == 2.0
    assert ng_feedstock.api_key_file == good_api_fn


@pytest.mark.unit
@pytest.mark.skipif(RG_NOT_INSTALLED, reason="reverse_geocoder is not installed")
def test_EIANaturalGasFeedstockConfig_with_coordinates():
    """Tests a failed API for basic parameterizations."""
    ng_feedstock = EIANaturalGasFeedstockConfig(
        resource_year=2022,
        price_category="WELLHEAD",
        latitude=best_trailer_in_colorado_coords[0],
        longitude=best_trailer_in_colorado_coords[1],
        monthly=True,
    )
    assert ng_feedstock.commodity == "natural_gas"
    assert ng_feedstock.commodity_rate_units == "MMBtu/h"
    assert ng_feedstock.commodity_amount_units == "MMBtu"
    assert ng_feedstock.filename is None
    assert ng_feedstock.price.size == 8760
    assert ng_feedstock.price.sum() == 0
    assert ng_feedstock.resource_year == 2022
    assert ng_feedstock.monthly
    assert ng_feedstock.price_category == "wellhead"
    assert ng_feedstock.state == "CO"
    assert ng_feedstock.cost_year == CURRENT_YEAR
    assert ng_feedstock.annual_cost == 0.0
    assert ng_feedstock.start_up_cost == 0.0


@pytest.mark.unit
def test_EIANaturalGasFeedstockCostModel_with_sites(subtests, EIA_API_key_file):
    """Create a basic feedstock configuration for testing."""
    api_key_fn, *_ = EIA_API_key_file
    tech_config = {
        "model_inputs": {
            "shared_parameters": {
                "commodity": "natural_gas",
                "commodity_rate_units": "MMBtu/h",
            },
            "performance_parameters": {
                "rated_capacity": 100.0,
            },
            "cost_parameters": {
                "price": 4.2,  # USD/MMBtu
                "annual_cost": 0,
                "start_up_cost": 0,
                "cost_year": 2023,
                "commodity_amount_units": "MMBtu",  # optional
                "monthly": True,
                "price_category": "industrial",
                "resource_year": 2023,
                "api_key_file": api_key_fn,
            },
        }
    }
    plant_config = {
        "plant": {"plant_life": 30, "simulation": {"n_timesteps": 8760, "dt": 3600}},
        "sites": {
            "site1": {
                "latitude": definitely_not_the_us_coords[0],
                "longitude": definitely_not_the_us_coords[1],
            },
            "site2": {
                "latitude": best_trailer_in_colorado_coords[0],
                "longitude": best_trailer_in_colorado_coords[1],
            },
        },
    }

    perf_model = FeedstockPerformanceModel(
        plant_config=plant_config, tech_config=tech_config, driver_config={}
    )
    site1_tech = deepcopy(tech_config)
    site1_tech["model_inputs"]["cost_parameters"]["site_name"] = None
    cost_model_site1 = EIANaturalGasFeedstockCostModel(
        plant_config=plant_config,
        tech_config=site1_tech,
        driver_config={},
    )
    site2_tech = deepcopy(site1_tech)
    site2_tech["model_inputs"]["cost_parameters"]["site_name"] = "site2"
    cost_model_site2 = EIANaturalGasFeedstockCostModel(
        plant_config=plant_config,
        tech_config=site2_tech,
        driver_config={},
    )
    no_site_tech = deepcopy(site1_tech)
    no_site_tech["model_inputs"]["cost_parameters"]["site_name"] = "site1"
    no_site_tech["model_inputs"]["cost_parameters"]["state"] = "CT"
    cost_model_state = EIANaturalGasFeedstockCostModel(
        plant_config=plant_config,
        tech_config=no_site_tech,
        driver_config={},
    )

    if not RG_NOT_INSTALLED:
        with subtests.test("First site when no inputs"):
            prob = om.Problem()
            prob.model.add_subsystem("ng_feedstock_source", perf_model)
            prob.model.add_subsystem("ng_feedstock", cost_model_site1)
            # Connect the feedstock performance model output to the cost model input
            prob.model.connect(
                "ng_feedstock_source.natural_gas_out",
                "ng_feedstock.natural_gas_out",
            )
            with pytest.raises(ValueError, match=r"'state' must be in(.*?)got 'Alberta'"):
                prob.setup()

    if not RG_NOT_INSTALLED:
        with subtests.test("Specified site"):
            prob = om.Problem()
            prob.model.add_subsystem("ng_feedstock_source", perf_model)
            prob.model.add_subsystem("ng_feedstock", cost_model_site2)
            # Connect the feedstock performance model output to the cost model input
            prob.model.connect(
                "ng_feedstock_source.natural_gas_out",
                "ng_feedstock.natural_gas_out",
            )
            with pytest.raises(HTTPError):
                prob.setup()
                assert prob.get_val("ng_feedstock.config.state") == "CO"

    with subtests.test("Uses cost configuration's state over site data"):
        prob = om.Problem()
        prob.model.add_subsystem("ng_feedstock_source", perf_model)
        prob.model.add_subsystem("ng_feedstock", cost_model_state)
        # Connect the feedstock performance model output to the cost model input
        prob.model.connect(
            "ng_feedstock_source.natural_gas_out",
            "ng_feedstock.natural_gas_out",
        )
        with pytest.raises(HTTPError):
            prob.setup()
            assert prob.get_val("ng_feedstock.config.state") == "CT"
