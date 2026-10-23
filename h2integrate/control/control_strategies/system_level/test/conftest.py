# ruff: disable[F401]
import pytest

from test.conftest import (
    temp_dir,
    temp_dir_module,
    temp_copy_of_example,
    pytest_collection_modifyitems,
    temp_copy_of_example_module_scope,
)


# ruff: enable[F401]


@pytest.fixture
def hetero_example():
    connections = [
        ["wind", "gen_combiner", "electricity", "cable"],
        ["solar", "gen_combiner", "electricity", "cable"],
        ["gen_combiner", "battery", "electricity", "cable"],
        ["gen_combiner", "elec_combiner", "electricity", "cable"],
        ["battery", "elec_combiner", "electricity", "cable"],
        ["elec_combiner", "electricity_splitter", "electricity", "cable"],
        ["electricity_splitter", "electrolyzer", "electricity", "cable"],
        ["electricity_splitter", "haber_bosch", "electricity", "cable"],
        ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
        ["n2_feedstock", "haber_bosch", "nitrogen", "pipe"],
        ["haber_bosch", "ammonia_load_demand", "ammonia", "pipe"],
    ]
    classifiers = {
        "wind": "flexible",
        "solar": "flexible",
        "battery": "storage",
        "electrolyzer": "dispatchable",
        "haber_bosch": "dispatchable",
        "n2_feedstock": "feedstock",
        "gen_combiner": "combiner",
        "elec_combiner": "combiner",
        "electricity_splitter": "splitter",
        "ammonia_load_demand": "demand",
    }
    return {
        "connections": connections,
        "classifiers": classifiers,
        "demand_tech": "ammonia_load_demand",
        "demand_commodity": "ammonia",
        "demand_rate_units": "kg/h",
        "commodity_units": {"electricity": "kW", "hydrogen": "kg/h", "nitrogen": "kg/h"},
    }


@pytest.fixture
def grid_to_haber_bosch():
    connections = [
        ["wind", "electrolyzer", "electricity", "cable"],
        ["electrolyzer", "haber_bosch", "hydrogen", "pipe"],
        ["grid", "haber_bosch", "electricity", "cable"],
        ["n2_feedstock", "haber_bosch", "nitrogen", "pipe"],
        ["haber_bosch", "ammonia_demand", "ammonia", "pipe"],
    ]
    classifiers = {
        "wind": "flexible",
        "grid": "dispatchable",
        "electrolyzer": "dispatchable",
        "haber_bosch": "dispatchable",
        "n2_feedstock": "feedstock",
        "ammonia_demand": "demand",
    }
    return {
        "connections": connections,
        "classifiers": classifiers,
        "demand_tech": "ammonia_demand",
        "demand_commodity": "ammonia",
        "demand_rate_units": "kg/h",
        "commodity_units": {"electricity": "kW", "hydrogen": "kg/h", "nitrogen": "kg/h"},
    }


@pytest.fixture
def fake_complex_system_816():
    connections = [
        ["ocean", "desalination", "salt_water", "pipe"],
        ["desalination", "electrolyzer", "fresh_water", "pipe"],
        ["wind", "elec_combiner", "electricity", "cable"],
        ["solar", "elec_combiner", "electricity", "cable"],
        ["elec_combiner", "battery", "electricity", "cable"],
        ["battery", "elec_combiner_2", "electricity", "cable"],
        ["elec_combiner", "elec_combiner_2", "electricity", "cable"],
        ["elec_combiner_2", "electrolyzer", "electricity", "cable"],
        ["electrolyzer", "h2_storage", "hydrogen", "pipe"],
        ["electrolyzer", "h2_combiner", "hydrogen", "pipe"],
        ["electrolyzer", "haber_bosch", "oxygen", "pipe"],
        ["electrolyzer", "haber_bosch", "heat", "pipe"],
        ["h2_storage", "h2_combiner", "hydrogen", "pipe"],
        ["h2_combiner", "haber_bosch", "hydrogen", "pipe"],
        ["grid", "haber_bosch", "electricity", "cable"],
        ["n2_feedstock", "haber_bosch", "nitrogen", "pipe"],
        ["haber_bosch", "nh3_storage", "ammonia", "pipe"],
        ["haber_bosch", "nh3_combiner", "ammonia", "pipe"],
        ["nh3_storage", "nh3_combiner", "ammonia", "pipe"],
        ["nh3_combiner", "nh3_load_demand", "ammonia", "pipe"],
    ]
    classifiers = {
        "ocean": "feedstock",
        "desalination": "dispatchable",
        "wind": "flexible",
        "solar": "flexible",
        "elec_combiner": "combiner",
        "battery": "storage",
        "elec_combiner_2": "combiner",
        "electrolyzer": "dispatchable",
        "h2_storage": "storage",
        "h2_combiner": "combiner",
        "haber_bosch": "dispatchable",
        "grid": "dispatchable",
        "n2_feedstock": "feedstock",
        "nh3_storage": "storage",
        "nh3_combiner": "combiner",
        "nh3_load_demand": "demand",
    }
    return {
        "connections": connections,
        "classifiers": classifiers,
        "demand_tech": "nh3_load_demand",
        "demand_commodity": "ammonia",
        "demand_rate_units": "kg/h",
        "commodity_units": {
            "electricity": "kW",
            "hydrogen": "kg/h",
            "oxygen": "kg/h",
            "heat": "kW",
            "fresh_water": "kg/h",
            "salt_water": "kg/h",
            "nitrogen": "kg/h",
        },
    }


@pytest.fixture
def nh3_with_storage_816():
    connections = [
        ["wind", "combiner", "electricity", "cable"],
        ["solar", "combiner", "electricity", "cable"],
        ["combiner", "battery", "electricity", "cable"],
        ["battery", "elec_combiner", "electricity", "cable"],
        ["combiner", "elec_combiner", "electricity", "cable"],
        ["elec_combiner", "electrolyzer", "electricity", "cable"],
        ["electrolyzer", "h2_storage", "hydrogen", "pipe"],
        ["electrolyzer", "h2_combiner", "hydrogen", "pipe"],
        ["h2_storage", "h2_combiner", "hydrogen", "pipe"],
        ["h2_combiner", "haber_bosch", "hydrogen", "pipe"],
        ["n2_feedstock", "haber_bosch", "nitrogen", "pipe"],
        ["electricity_feedstock", "haber_bosch", "electricity", "cable"],
        ["haber_bosch", "nh3_storage", "ammonia", "pipe"],
        ["nh3_storage", "nh3_combiner", "ammonia", "pipe"],
        ["haber_bosch", "nh3_combiner", "ammonia", "pipe"],
        ["nh3_combiner", "nh3_load_demand", "ammonia", "pipe"],
    ]
    classifiers = {
        "wind": "flexible",
        "solar": "flexible",
        "combiner": "combiner",
        "battery": "storage",
        "elec_combiner": "combiner",
        "electrolyzer": "dispatchable",
        "h2_storage": "storage",
        "h2_combiner": "combiner",
        "haber_bosch": "dispatchable",
        "n2_feedstock": "feedstock",
        "electricity_feedstock": "feedstock",
        "nh3_storage": "storage",
        "nh3_combiner": "combiner",
        "nh3_load_demand": "demand",
    }
    return {
        "connections": connections,
        "classifiers": classifiers,
        "demand_tech": "nh3_load_demand",
        "demand_commodity": "ammonia",
        "demand_rate_units": "kg/h",
        "commodity_units": {"electricity": "kW", "hydrogen": "kg/h", "nitrogen": "kg/h"},
    }


@pytest.fixture
def complex_multi_commodity_816():
    connections = [
        ["wind", "combiner", "electricity", "cable"],
        ["solar", "combiner", "electricity", "cable"],
        ["combiner", "battery", "electricity", "cable"],
        ["battery", "elec_combiner", "electricity", "cable"],
        ["combiner", "elec_combiner", "electricity", "cable"],
        ["elec_combiner", "electrolyzer", "electricity", "cable"],
        ["electrolyzer", "h2_storage", "hydrogen", "pipe"],
        ["electrolyzer", "h2_combiner", "hydrogen", "pipe"],
        ["h2_storage", "h2_combiner", "hydrogen", "pipe"],
        ["h2_combiner", "haber_bosch", "hydrogen", "pipe"],
        ["n2_feedstock", "haber_bosch", "nitrogen", "pipe"],
        ["electricity_feedstock", "haber_bosch", "electricity", "cable"],
        ["haber_bosch", "nh3_load_demand", "ammonia", "pipe"],
    ]
    classifiers = {
        "wind": "flexible",
        "solar": "flexible",
        "combiner": "combiner",
        "battery": "storage",
        "elec_combiner": "combiner",
        "electrolyzer": "dispatchable",
        "h2_storage": "storage",
        "h2_combiner": "combiner",
        "haber_bosch": "dispatchable",
        "n2_feedstock": "feedstock",
        "electricity_feedstock": "feedstock",
        "nh3_load_demand": "demand",
    }
    return {
        "connections": connections,
        "classifiers": classifiers,
        "demand_tech": "nh3_load_demand",
        "demand_commodity": "ammonia",
        "demand_rate_units": "kg/h",
        "commodity_units": {"electricity": "kW", "hydrogen": "kg/h", "nitrogen": "kg/h"},
    }


@pytest.fixture
def slc_topologies(
    hetero_example,
    grid_to_haber_bosch,
    fake_complex_system_816,
    nh3_with_storage_816,
    complex_multi_commodity_816,
):
    return {
        "hetero_example": hetero_example,
        "grid_to_haber_bosch": grid_to_haber_bosch,
        "fake_complex_system_816": fake_complex_system_816,
        "nh3_with_storage_816": nh3_with_storage_816,
        "complex_multi_commodity_816": complex_multi_commodity_816,
    }
