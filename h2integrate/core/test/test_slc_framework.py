from pathlib import Path

import pytest
import networkx as nx
from pytest import fixture

from h2integrate import H2IntegrateModel, load_yaml


@fixture
def plant_config(connection_case):
    plant_config = load_yaml(Path(__file__).parent / "inputs" / "tech_connection_cases.yaml")
    return plant_config[connection_case]


@fixture
def tech_control_classifiers(connection_case):
    config = load_yaml(Path(__file__).parent / "inputs" / "tech_connection_cases.yaml")
    tech_connections = config[connection_case]["technology_interconnections"]
    source_techs = {connection[0] for connection in tech_connections}
    dest_techs = {connection[1] for connection in tech_connections}
    all_techs = source_techs | dest_techs

    tech_control_classification = {}
    for tech in all_techs:
        if (classifier := config["control_classifiers"].get(tech, None)) is not None:
            tech_control_classification[tech] = classifier
            continue
        if "combiner" in tech or "splitter" in tech:
            tech_control_classification[tech] = "connector"
            continue

    tech_control_classification = {
        tech: config["control_classifiers"].get(tech, "connector") for tech in all_techs
    }
    return tech_control_classification


def make_mock_tech_config(demand_tech, storage_techs, demand_class_name="GenericDemandComponent"):
    demand_config = {
        demand_tech: {
            "performance_model": {"model": demand_class_name},
            "model_inputs": {
                "performance_parameters": {
                    "commodity": "electricity",
                    "commodity_rate_units": "kW",
                }
            },
        }
    }
    if len(storage_techs) == 0:
        return {"technologies": demand_config}
    storage_configs = {tech: {} for tech in storage_techs}

    return {"technologies": demand_config | storage_configs}


@pytest.mark.unit
@pytest.mark.parametrize("connection_case", ["complex_electrical"])
def test_slc_topology_missing_demand(plant_config, tech_control_classifiers, subtests):
    # initialize the model
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    # remove the demand component from the SLC input
    plant_config["system_level_control"].pop("demand_component")
    model.plant_config = plant_config
    model.tech_control_classifiers = tech_control_classifiers
    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    tech_config = make_mock_tech_config("electrical_load_demand", storage_techs)
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    # check that error is thrown
    with subtests.test("Error raised when missing demand_component"):
        with pytest.raises(ValueError) as excinfo:
            model._classify_slc_technologies()
            assert "Please specify the technology name for the demand component in" in str(
                excinfo.value
            )


@pytest.mark.unit
@pytest.mark.parametrize("connection_case", ["complex_electrical"])
def test_slc_topology_demand_not_in_tech(plant_config, tech_control_classifiers, subtests):
    # initialize the model
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    model.plant_config = plant_config
    model.tech_control_classifiers = tech_control_classifiers
    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    tech_config = make_mock_tech_config("unused_load_demand", storage_techs)
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    # check that error is thrown
    with subtests.test("Error raised when missing demand_component in tech config"):
        demand_tech = plant_config["system_level_control"]["demand_component"]
        with pytest.raises(ValueError) as excinfo:
            model._classify_slc_technologies()
            assert f"``{demand_tech}`` not defined in the tech configuration file." in str(
                excinfo.value
            )


@pytest.mark.unit
@pytest.mark.parametrize("connection_case", ["complex_electrical"])
def test_slc_topology_invalid_demand_tech(plant_config, tech_control_classifiers, subtests):
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    model.plant_config = plant_config
    model.tech_control_classifiers = tech_control_classifiers
    demand_tech = plant_config["system_level_control"]["demand_component"]
    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    tech_config = make_mock_tech_config(
        demand_tech, storage_techs, demand_class_name="AmmoniaPlant"
    )
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    with subtests.test("Error raised when demand component is invalid"):
        demand_tech = plant_config["system_level_control"]["demand_component"]
        with pytest.raises(ValueError) as excinfo:
            model._classify_slc_technologies()
            assert (
                "Demand component ``AmmoniaPlant`` is not a supported model for the system level"
                in str(excinfo.value)
            )


@pytest.mark.unit
@pytest.mark.parametrize("connection_case", ["complex_electrical"])
def test_slc_topology_unconnected_demand(plant_config, tech_control_classifiers, subtests):
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    demand_tech = plant_config["system_level_control"]["demand_component"]

    # remove the tech connection for the demand component
    tech_connections = plant_config["technology_interconnections"]
    i_drop = [i for i, connection in enumerate(tech_connections) if connection[1] == demand_tech]
    tech_connections.pop(i_drop[0])

    model.plant_config = plant_config
    model.tech_control_classifiers = tech_control_classifiers

    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    tech_config = make_mock_tech_config(demand_tech, storage_techs)
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    with subtests.test("Error raised when demand component is unconnected"):
        demand_tech = plant_config["system_level_control"]["demand_component"]
        with pytest.raises(ValueError) as excinfo:
            model._classify_slc_technologies()
            assert (
                f"Please ensure that the demand technology ``{demand_tech}`` is connected"
                in str(excinfo.value)
            )


@pytest.mark.unit
@pytest.mark.parametrize("connection_case", ["hydrogen_system"])
def test_slc_topology_h2_system(plant_config, tech_control_classifiers, subtests):
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    model.plant_config = plant_config
    model.tech_control_classifiers = tech_control_classifiers
    demand_tech = plant_config["system_level_control"]["demand_component"]
    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    tech_config = make_mock_tech_config(demand_tech, storage_techs)
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    slc_topology = model._classify_slc_technologies()

    with subtests.test("SLC topology demand tech"):
        assert slc_topology["demand_tech"] == demand_tech

    slc_techs = set(slc_topology["technology_graph"].nodes())
    all_techs = set(model.technology_graph.nodes())
    upstream_techs = nx.ancestors(model.technology_graph, demand_tech)

    with subtests.test("Demand tech is included in SLC graph"):
        assert demand_tech in slc_techs

    with subtests.test("All techs in SLC graph"):
        assert slc_techs == all_techs

    with subtests.test("All upstream techs in SLC graph"):
        assert upstream_techs == slc_techs.difference({demand_tech})


@pytest.mark.unit
@pytest.mark.parametrize("connection_case", ["ammonia_system_nh3_dmd"])
def test_slc_topology_nh3_system(plant_config, tech_control_classifiers, subtests):
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    model.plant_config = plant_config
    model.tech_control_classifiers = tech_control_classifiers
    demand_tech = plant_config["system_level_control"]["demand_component"]
    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    tech_config = make_mock_tech_config(demand_tech, storage_techs)
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    slc_topology = model._classify_slc_technologies()

    with subtests.test("SLC topology demand tech"):
        assert slc_topology["demand_tech"] == demand_tech

    slc_techs = set(slc_topology["technology_graph"].nodes())
    all_techs = set(model.technology_graph.nodes())
    upstream_techs = nx.ancestors(model.technology_graph, demand_tech)

    with subtests.test("Demand tech is included in SLC graph"):
        assert demand_tech in slc_techs

    with subtests.test("All techs in SLC graph"):
        assert slc_techs == all_techs

    with subtests.test("All upstream techs in SLC graph"):
        assert upstream_techs == slc_techs.difference({demand_tech})


@pytest.mark.unit
@pytest.mark.parametrize("connection_case", ["ammonia_system_nh3_dmd_with_upstream_demand"])
def test_slc_topology_nh3_system_upstream_demand(plant_config, tech_control_classifiers, subtests):
    # theres a demand component upstream of the demand_tech
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    model.plant_config = plant_config
    model.tech_control_classifiers = tech_control_classifiers
    demand_tech = plant_config["system_level_control"]["demand_component"]
    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    tech_config = make_mock_tech_config(demand_tech, storage_techs)
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    slc_topology = model._classify_slc_technologies()

    with subtests.test("SLC topology demand tech"):
        assert slc_topology["demand_tech"] == demand_tech

    slc_techs = set(slc_topology["technology_graph"].nodes())
    all_techs = set(model.technology_graph.nodes())
    upstream_techs = nx.ancestors(model.technology_graph, demand_tech)

    with subtests.test("Demand tech is included in SLC graph"):
        assert demand_tech in slc_techs

    with subtests.test("No downstream techs in SLC graph"):
        # check that techs downstream of h2_demand are not included
        assert all_techs == slc_techs

    with subtests.test("All upstream techs in SLC graph"):
        assert upstream_techs == slc_techs.difference({demand_tech})

    with subtests.test("Upstream demand tech not included in tech_to_commodity"):
        assert not any(
            tech_commod[0] == "h2_load_demand" for tech_commod in slc_topology["tech_to_commodity"]
        )


@pytest.mark.unit
@pytest.mark.parametrize("connection_case", ["ammonia_system_h2_dmd"])
def test_slc_topology_nh3_system_with_h2_demand(plant_config, tech_control_classifiers, subtests):
    # demand_tech is downstream of another demand component
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    model.plant_config = plant_config
    model.tech_control_classifiers = tech_control_classifiers
    demand_tech = plant_config["system_level_control"]["demand_component"]
    storage_techs = [k for k, v in tech_control_classifiers.items() if v == "storage"]
    tech_config = make_mock_tech_config(demand_tech, storage_techs)
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    slc_topology = model._classify_slc_technologies()

    with subtests.test("SLC topology demand tech"):
        assert slc_topology["demand_tech"] == demand_tech

    slc_techs = set(slc_topology["technology_graph"].nodes())
    all_techs = set(model.technology_graph.nodes())
    upstream_techs = nx.ancestors(model.technology_graph, demand_tech)

    with subtests.test("Demand tech is included in SLC graph"):
        assert demand_tech in slc_techs

    with subtests.test("No downstream techs in SLC graph"):
        # check that techs downstream of h2_demand are not included
        downstream_techs = {"n2_feedstock", "ng_feedstock", "haber_bosch", "natural_gas_plant"}
        assert all_techs.difference(slc_techs) == downstream_techs

    with subtests.test("All upstream techs in SLC graph"):
        assert upstream_techs == slc_techs.difference({demand_tech})
