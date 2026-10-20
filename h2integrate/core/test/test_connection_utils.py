import pytest

from h2integrate.core.connection_utils import check_resource_models_are_connected


@pytest.mark.unit
def test_check_resource_models_are_connected(subtests):
    sites = {"site": {"resources": {"wind_resource": {}, "solar_resource": {}}}}

    with subtests.test("all resources connected"):
        connections = [
            ["site.wind_resource", "wind", "wind_resource_data"],
            ["site.solar_resource", "solar", "solar_resource_data"],
        ]
        check_resource_models_are_connected(sites, connections)

    with subtests.test("site-level connections without resources"):
        check_resource_models_are_connected(
            {"site": {}}, [["site", "wind", ["latitude", "latitude"]]]
        )

    with subtests.test("unconnected resource"):
        connections = [["site.wind_resource", "wind", "wind_resource_data"]]
        with pytest.raises(ValueError, match="not connected to a technology"):
            check_resource_models_are_connected(sites, connections)

    with subtests.test("undefined resource"):
        connections = [
            ["site.wind_resource", "wind", "wind_resource_data"],
            ["site.solar_resource", "solar", "solar_resource_data"],
            ["site.tidal_resource", "tidal", "tidal_resource_data"],
        ]
        with pytest.raises(ValueError, match=r"Missing resource\(s\) are not defined"):
            check_resource_models_are_connected(sites, connections)
