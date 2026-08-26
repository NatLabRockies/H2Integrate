import os
import shutil
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import yaml
import numpy as np
import pytest

import h2integrate.core.h2integrate_model as h2i_model_module
from h2integrate import (
    ROOT_DIR,
    EXAMPLE_DIR,
    H2IntegrateModel,
    load_tech_yaml,
    load_plant_yaml,
    load_driver_yaml,
)


@pytest.mark.integration
@pytest.mark.parametrize("example_folder,resource_example_folder", [("01_onshore_steel_mn", None)])
def test_missing_tech_interconnections(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example
    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")
    # remove technology interconnections
    plant_config.pop("technology_interconnections")
    top_level_config = {
        "plant_config": plant_config,
        "technology_config": tech_config,
        "driver_config": driver_config,
    }

    expected_error_start = (
        "9 technologies have been defined in the technology config but are not connected"
    )

    with subtests.test("Commodity not input to destination"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel(top_level_config)
        err = str(excinfo.value)
        assert expected_error_start in err


@pytest.mark.integration
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("17_splitter_wind_doc_h2", None)]
)
def test_use_commodity_stream_timeseries_finances_error(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example
    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")

    # Remove commodity_stream_output from finace subgroup
    plant_config["finance_parameters"]["finance_subgroups"]["electricity_doc"].pop(
        "commodity_stream_output"
    )
    top_level_config = {
        "plant_config": plant_config,
        "technology_config": tech_config,
        "driver_config": driver_config,
    }

    with pytest.raises(ValueError) as excinfo:
        H2IntegrateModel(top_level_config)
    err = str(excinfo.value)
    with subtests.test("Commodity stream name is missing error message parts"):
        assert "`commodity_stream_output` is a required input" in err
        assert "`use_commodity_stream_timeseries` is True" in err
        assert "finance subgroup `electricity_doc`" in err


@pytest.mark.integration
@pytest.mark.parametrize("example_folder,resource_example_folder", [("01_onshore_steel_mn", None)])
def test_check_tech_interconnections(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example
    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")
    tech_interconnections = plant_config["technology_interconnections"].copy()
    idx_electrolyzer_connect = [
        i
        for i, connection in enumerate(tech_interconnections)
        if connection[0] == "electrolyzer" and len(connection) == 4
    ]
    idx_electrolyzer_to_combiner = [
        i for i in idx_electrolyzer_connect if tech_interconnections[i][1] == "h2_combiner"
    ]
    # update so that trying to connect oxygen out of electrolyzer to h2_combiner
    # should get error because h2_combiner doesn't have an input for oxygen
    tech_interconnections[idx_electrolyzer_to_combiner[0]] = [
        "electrolyzer",
        "h2_combiner",
        "oxygen",
        "pipe",
    ]
    plant_config["technology_interconnections"] = tech_interconnections
    top_level_config = {
        "plant_config": plant_config,
        "technology_config": tech_config,
        "driver_config": driver_config,
    }
    h2i = H2IntegrateModel(top_level_config)

    with subtests.test("Commodity not input to destination"):
        with pytest.raises(ValueError) as excinfo:
            h2i.setup()
        err = str(excinfo.value)
        assert "do not accept their specified input commodity" in err
        assert "`h2_combiner` <- `oxygen`" in err
        assert "Update `technology_interconnections`" in err

    # Fix the plant config from the previous test
    tech_interconnections[idx_electrolyzer_to_combiner[0]] = [
        "electrolyzer",
        "h2_combiner",
        "hydrogen",
        "pipe",
    ]
    idx_h2_storage_connect = [
        i
        for i, connection in enumerate(tech_interconnections)
        if connection[0] == "h2_storage" and len(connection) == 4
    ]
    # Update so that steel (which has no existing L4 connections and does not output
    # hydrogen) is connected to h2_combiner. This tests that _check_tech_connections
    # raises a commodity error without triggering the storage topology check that
    # would fire if we used battery (a storage tech that already has an out-stream).
    tech_interconnections[idx_h2_storage_connect[0]] = [
        "steel",
        "h2_combiner",
        "hydrogen",
        "pipe",
    ]
    plant_config["technology_interconnections"] = tech_interconnections
    top_level_config = {
        "plant_config": plant_config,
        "technology_config": tech_config,
        "driver_config": driver_config,
    }
    h2i = H2IntegrateModel(top_level_config)

    with subtests.test("Commodity not output from source"):
        with pytest.raises(ValueError) as excinfo:
            h2i.setup()
        err = str(excinfo.value)
        assert "do not output their specified commodity" in err
        assert "`steel` -> `hydrogen`" in err
        assert "Update `technology_interconnections`" in err


@pytest.mark.integration
@pytest.mark.parametrize("example_folder,resource_example_folder", [("01_onshore_steel_mn", None)])
def test_validate_technology_interconnections(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example
    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")
    base_interconnections = plant_config["technology_interconnections"].copy()

    def _make_model(interconnections):
        cfg = {
            "plant_config": {**plant_config, "technology_interconnections": interconnections},
            "technology_config": tech_config,
            "driver_config": driver_config,
        }
        return H2IntegrateModel(cfg)

    # --- Check 1: discouraged length-3 [commodity_out, commodity_in] connection ---
    with subtests.test("length-3 _out/_in pair raises error"):
        bad_connections = [
            *base_interconnections,
            ["electrolyzer", "steel", ["hydrogen_out", "hydrogen_in"]],
        ]
        h2i = _make_model(bad_connections)
        with pytest.raises(ValueError) as excinfo:
            h2i.setup()
        err = str(excinfo.value)
        assert "Use a length-4 connection instead" in err
        assert "hydrogen" in err

    # --- Check 2a: storage tech with 0 inputs raises error ---
    with subtests.test("storage tech with no inputs raises error"):
        # Remove the connection that feeds h2_storage
        no_input_connections = [
            c
            for c in base_interconnections
            if not (c[0] == "electrolyzer" and c[1] == "h2_storage")
        ]
        h2i = _make_model(no_input_connections)
        with pytest.raises(ValueError) as excinfo:
            h2i.setup()
        err = str(excinfo.value)
        assert "h2_storage" in err
        assert "has no input connections in" in err
    with subtests.test("storage tech with 2 outputs raises error"):
        extra_out_connections = [
            *base_interconnections,
            ["h2_storage", "steel", "hydrogen", "pipe"],
        ]
        h2i = _make_model(extra_out_connections)
        with pytest.raises(ValueError) as excinfo:
            h2i.setup()
        err = str(excinfo.value)
        assert "h2_storage" in err
        assert "but should have at most 1." in err

    # --- Check 2c: upstream of storage with >2 outputs raises error ---
    with subtests.test("upstream tech of storage with >2 outputs raises error"):
        extra_upstream_connections = [
            *base_interconnections,
            ["electrolyzer", "steel", "hydrogen", "pipe"],
        ]
        h2i = _make_model(extra_upstream_connections)
        with pytest.raises(ValueError) as excinfo:
            h2i.setup()
        err = str(excinfo.value)
        assert "electrolyzer" in err
        assert "feeds storage technology" in err
        assert "at most 2 output streams" in err
    with subtests.test("technology with 2 outputs (no storage) raises error"):
        # Add a second output from wind (which is not a splitter and not upstream of storage)
        extra_wind_connections = [
            *base_interconnections,
            ["wind", "h2_combiner", "electricity", "cable"],
        ]
        h2i = _make_model(extra_wind_connections)
        with pytest.raises(ValueError) as excinfo:
            h2i.setup()
        err = str(excinfo.value)
        assert "wind" in err
        assert "Consider using a splitter component." in err
    with subtests.test("technology with 2 inputs raises error"):
        # Use h2_combiner as the second source so that the source itself (being a combiner)
        # is excluded from check #3, allowing the per-commodity source check to fire on
        # electrolyzer (which already receives electricity from elec_combiner).
        extra_input_connections = [
            *base_interconnections,
            ["h2_combiner", "electrolyzer", "electricity", "cable"],
        ]
        h2i = _make_model(extra_input_connections)
        with pytest.raises(ValueError) as excinfo:
            h2i.setup()
        err = str(excinfo.value)
        assert "electrolyzer" in err
        assert "Consider using a combiner component." in err


# ---------------------------------------------------------------------------
# Lightweight unit tests for _validate_technology_interconnections
#
# These tests bypass OpenMDAO setup entirely by constructing a minimal fake
# model object that only carries the three attributes that the validator
# reads: ``plant_config``, ``technology_graph``, and
# ``tech_control_classifiers``.  This allows complex multi-commodity
# topologies to be exercised without needing real H2I component classes.
# ---------------------------------------------------------------------------

import types


def _make_fake_model(interconnections, classifiers):
    """Build a minimal stub for testing _validate_technology_interconnections.

    Args:
        interconnections: list of technology interconnection entries (same
            format as ``plant_config["technology_interconnections"]``).
        classifiers: dict mapping tech name to its ``_control_classifier``
            string (e.g. ``{"battery": "storage", "combiner": "combiner"}``).

    Returns:
        types.SimpleNamespace: object with ``plant_config``,
            ``technology_graph``, and ``tech_control_classifiers`` set.
    """
    fake = types.SimpleNamespace()
    fake.plant_config = {"technology_interconnections": interconnections}
    # create_technology_graph does not access any other attribute of self,
    # so passing the stub as ``self`` is safe.
    fake.technology_graph = H2IntegrateModel.create_technology_graph(fake, interconnections)
    fake.tech_control_classifiers = classifiers
    return fake


@pytest.mark.unit
def test_validate_interconnections_multi_commodity_storage(subtests):
    """Storage tech with two different-commodity inputs should be allowed.

    Models a future storage that accepts both electricity (for charging) and
    hydrogen (as the stored commodity) from two separate upstream technologies.
    Each commodity has exactly one source, so no error should be raised.
    """
    interconnections = [
        ["source_elec", "storage", "electricity", "cable"],
        ["source_h2", "storage", "hydrogen", "pipe"],
        ["storage", "h2_combiner", "hydrogen", "pipe"],
    ]
    classifiers = {
        "storage": "storage",
        "h2_combiner": "combiner",
    }
    fake = _make_fake_model(interconnections, classifiers)

    with subtests.test("two-commodity storage passes validation"):
        H2IntegrateModel._validate_technology_interconnections(fake)  # must not raise

    # Same commodity (hydrogen) from two different sources into storage must fail.
    bad_interconnections = [
        ["source_h2_a", "storage", "hydrogen", "pipe"],
        ["source_h2_b", "storage", "hydrogen", "pipe"],
    ]
    bad = _make_fake_model(bad_interconnections, {"storage": "storage"})

    with subtests.test("duplicate hydrogen sources into storage raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(bad)
        err = str(excinfo.value)
        assert "storage" in err
        assert "but should receive it from at most 1." in err


@pytest.mark.unit
def test_validate_interconnections_multi_in_multi_out_converter(subtests):
    """Converter with two different input commodities and two different output
    commodities should pass validation.

    Models an ammonia-synloop-style converter that consumes hydrogen and
    nitrogen and produces both ammonia and a purge-gas stream.  Each commodity
    flows from/to exactly one technology, so no topology error should occur.
    """
    interconnections = [
        ["h2_source", "converter", "hydrogen", "pipe"],
        ["n2_source", "converter", "nitrogen", "pipe"],
        ["converter", "ammonia_dest", "ammonia", "pipe"],
        ["converter", "purge_dest", "purge_gas", "pipe"],
    ]
    classifiers = {"converter": "dispatchable"}
    fake = _make_fake_model(interconnections, classifiers)

    with subtests.test("two-in two-out converter passes validation"):
        H2IntegrateModel._validate_technology_interconnections(fake)  # must not raise

    # Same commodity to two destinations without a splitter must fail.
    bad_interconnections = [
        ["h2_source", "converter", "hydrogen", "pipe"],
        ["n2_source", "converter", "nitrogen", "pipe"],
        ["converter", "dest_a", "ammonia", "pipe"],
        ["converter", "dest_b", "ammonia", "pipe"],  # ammonia goes to two places
    ]
    bad = _make_fake_model(bad_interconnections, {"converter": "dispatchable"})

    with subtests.test("same output commodity to two destinations raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(bad)
        err = str(excinfo.value)
        assert "converter" in err
        assert "Consider using a splitter component." in err

    # Same commodity from two sources into converter must also fail.
    bad_interconnections_in = [
        ["h2_source_a", "converter", "hydrogen", "pipe"],
        ["h2_source_b", "converter", "hydrogen", "pipe"],  # duplicate hydrogen source
        ["n2_source", "converter", "nitrogen", "pipe"],
        ["converter", "ammonia_dest", "ammonia", "pipe"],
    ]
    bad_in = _make_fake_model(bad_interconnections_in, {"converter": "dispatchable"})

    with subtests.test("same input commodity from two sources raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(bad_in)
        err = str(excinfo.value)
        assert "converter" in err
        assert "Consider using a combiner component." in err


@pytest.mark.unit
def test_validate_interconnections_splitter_combiner_exempt(subtests):
    """Splitter and combiner technologies are exempt from the per-commodity
    max-1 checks because by design they fan out or merge streams.

    A splitter sending the same commodity to multiple destinations, and a
    combiner receiving the same commodity from multiple sources, must both
    pass without error.
    """
    interconnections = [
        # splitter fans one hydrogen stream out to two consumers
        ["h2_source", "h2_splitter", "hydrogen", "pipe"],
        ["h2_splitter", "consumer_a", "hydrogen", "pipe"],
        ["h2_splitter", "consumer_b", "hydrogen", "pipe"],
        # combiner merges two electricity sources into one
        ["wind", "elec_combiner", "electricity", "cable"],
        ["solar", "elec_combiner", "electricity", "cable"],
        ["elec_combiner", "electrolyzer", "electricity", "cable"],
    ]
    classifiers = {
        "h2_splitter": "splitter",
        "elec_combiner": "combiner",
        "consumer_a": "dispatchable",
        "consumer_b": "dispatchable",
        "electrolyzer": "dispatchable",
    }
    fake = _make_fake_model(interconnections, classifiers)

    with subtests.test("splitter and combiner exempt from max-1 checks"):
        H2IntegrateModel._validate_technology_interconnections(fake)  # must not raise


@pytest.mark.unit
def test_validate_interconnections_storage_no_inputs_raises(subtests):
    """Storage technology with no L4 inputs must raise a clear error."""
    # Only an output connection; no input to storage
    interconnections = [
        ["storage", "combiner", "hydrogen", "pipe"],
    ]
    classifiers = {"storage": "storage", "combiner": "combiner"}
    fake = _make_fake_model(interconnections, classifiers)

    with subtests.test("storage with no inputs raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(fake)
        err = str(excinfo.value)
        assert "storage" in err
        assert "has no input connections in" in err


@pytest.mark.unit
def test_validate_interconnections_length3_commodity_pair_raises(subtests):
    """A length-3 connection whose parameter list matches [X_out, X_in] must
    raise an error directing the user to use the length-4 format."""
    interconnections = [
        ["wind", "electrolyzer", ["electricity_out", "electricity_in"]],
    ]
    classifiers = {"electrolyzer": "dispatchable"}
    fake = _make_fake_model(interconnections, classifiers)

    with subtests.test("length-3 _out/_in pair raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(fake)
        err = str(excinfo.value)
        assert "electricity" in err
        assert "Use a length-4 connection instead" in err


@pytest.mark.unit
def test_validate_interconnections_length3_commodity_pair_with_slices_raises(subtests):
    """A length-3 [X_out[...], X_in[...]] parameter pair must raise the
    same guidance to use a length-4 commodity connection."""
    interconnections = [
        ["wind", "electrolyzer", ["electricity_out[0:4]", "electricity_in[0:4]"]],
    ]
    classifiers = {"electrolyzer": "dispatchable"}
    fake = _make_fake_model(interconnections, classifiers)

    with subtests.test("length-3 _out/_in pair with slices raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(fake)
        err = str(excinfo.value)
        assert "electricity" in err
        assert "Use a length-4 connection instead" in err


@pytest.mark.unit
def test_validate_interconnections_demand_component_not_counted_as_destination(subtests):
    """A source sending a commodity to both a real consumer and a demand-classified
    reporting component must pass validation.

    Demand components are observers/sinks that report on a commodity stream
    but do not consume it in a topology sense. They should not count against
    the source's per-commodity output-destination limit, allowing a pattern like:

        wind -> electricity -> electrolyzer   (real consumer)
        wind -> electricity -> demand_reporter (reporting only)

    The two-real-consumer case (no demand component involved) must still fail.
    """
    interconnections_valid = [
        ["wind", "electrolyzer", "electricity", "cable"],
        ["wind", "demand_reporter", "electricity", "cable"],
    ]
    classifiers_valid = {
        "wind": "flexible",
        "electrolyzer": "dispatchable",
        "demand_reporter": "demand",
    }
    fake_valid = _make_fake_model(interconnections_valid, classifiers_valid)

    with subtests.test("source to real consumer + demand reporter passes validation"):
        H2IntegrateModel._validate_technology_interconnections(fake_valid)  # must not raise

    # Two real (non-demand) consumers of the same commodity from one source must still fail.
    interconnections_bad = [
        ["wind", "electrolyzer", "electricity", "cable"],
        ["wind", "grid", "electricity", "cable"],
    ]
    classifiers_bad = {
        "wind": "flexible",
        "electrolyzer": "dispatchable",
        "grid": "dispatchable",
    }
    fake_bad = _make_fake_model(interconnections_bad, classifiers_bad)

    with subtests.test("source to two real consumers still raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(fake_bad)
        err = str(excinfo.value)
        assert "wind" in err
        assert "Consider using a splitter component." in err

    # Sending to a demand component that re-emits to a real consumer is valid on its
    # own; wind routes all electricity through the demand component to grid_sell.
    interconnections_demand_passthrough = [
        ["wind", "demand_comp", "electricity", "cable"],
        ["demand_comp", "grid_sell", "electricity", "cable"],
    ]
    classifiers_demand_passthrough = {
        "wind": "flexible",
        "demand_comp": "demand",
        "grid_sell": "dispatchable",
    }
    fake_passthrough = _make_fake_model(
        interconnections_demand_passthrough, classifiers_demand_passthrough
    )

    with subtests.test("demand component acting as pass-through to real consumer passes"):
        H2IntegrateModel._validate_technology_interconnections(fake_passthrough)  # must not raise

    # Double-counting: wind sends electricity to electrolyzer directly AND through a
    # demand component to grid_sell. The same electricity is counted in both paths.
    interconnections_double_count = [
        ["wind", "electrolyzer", "electricity", "cable"],
        ["wind", "demand_reporter", "electricity", "cable"],
        ["demand_reporter", "grid_sell", "electricity", "cable"],
    ]
    classifiers_double_count = {
        "wind": "flexible",
        "electrolyzer": "dispatchable",
        "demand_reporter": "demand",
        "grid_sell": "dispatchable",
    }
    fake_double_count = _make_fake_model(interconnections_double_count, classifiers_double_count)

    with subtests.test("source to direct real consumer AND outputting demand raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(fake_double_count)
        err = str(excinfo.value)
        assert "wind" in err
        assert "double-count" in err

    # Daisy-chain through two demand components then to a real consumer is valid as
    # long as wind does not also have a competing direct path to a real consumer.
    interconnections_daisy_valid = [
        ["wind", "demand_reporter", "electricity", "cable"],
        ["demand_reporter", "nested_demand", "electricity", "cable"],
        ["nested_demand", "grid_sell", "electricity", "cable"],
    ]
    classifiers_daisy_valid = {
        "wind": "flexible",
        "demand_reporter": "demand",
        "nested_demand": "demand",
        "grid_sell": "dispatchable",
    }
    fake_daisy_valid = _make_fake_model(interconnections_daisy_valid, classifiers_daisy_valid)

    with subtests.test("daisy-chained demand components as sole path to real consumer passes"):
        H2IntegrateModel._validate_technology_interconnections(fake_daisy_valid)  # must not raise

    # Same daisy-chain but wind also has a direct real consumer - should fail.
    interconnections_daisy_double = [
        ["wind", "electrolyzer", "electricity", "cable"],
        ["wind", "demand_reporter", "electricity", "cable"],
        ["demand_reporter", "nested_demand", "electricity", "cable"],
        ["nested_demand", "grid_sell", "electricity", "cable"],
    ]
    classifiers_daisy_double = {
        "wind": "flexible",
        "electrolyzer": "dispatchable",
        "demand_reporter": "demand",
        "nested_demand": "demand",
        "grid_sell": "dispatchable",
    }
    fake_daisy_double = _make_fake_model(interconnections_daisy_double, classifiers_daisy_double)

    with subtests.test("daisy-chained demand with competing direct path raises error"):
        with pytest.raises(ValueError) as excinfo:
            H2IntegrateModel._validate_technology_interconnections(fake_daisy_double)
        err = str(excinfo.value)
        assert "wind" in err
        assert "double-count" in err


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("07_run_of_river_plant", None)]
)
def test_custom_resource_model(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    from h2integrate.resource.river import RiverResource

    resource_model_fpath_parts = [ROOT_DIR] + RiverResource.__module__.split(".")[1:]
    resource_model_fpath_parts[-1] = f"{resource_model_fpath_parts[-1]}.py"

    # Make folder to hold custom resource model
    custom_resource_model_dir = temp_copy_of_example / "user_defined_resource"
    custom_resource_model_fpath = custom_resource_model_dir / "river_resource_model.py"
    Path(custom_resource_model_dir).mkdir(exist_ok=True)

    # Copy RiverResource model to custom resource model folder
    h2i_resource_model_fpath = Path(*resource_model_fpath_parts)
    shutil.copy(h2i_resource_model_fpath, custom_resource_model_fpath)

    # Change the name of the copied RiverResource model
    new_text = custom_resource_model_fpath.read_text().replace(
        "RiverResource", "CustomRiverResource"
    )
    custom_resource_model_fpath.write_text(new_text, encoding="utf-8")

    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    driver_config = load_driver_yaml(example_folder / "driver_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")

    # modify the plant config to use a custom resource
    custom_resource_model_inputs = {
        "resource_model": "CustomRiverResource",
        "resource_model_location": str(custom_resource_model_fpath.absolute()),
        "resource_parameters": plant_config["sites"]["site"]["resources"]["river_resource"][
            "resource_parameters"
        ],
    }
    plant_config["sites"]["site"]["resources"].update(
        {"river_resource": custom_resource_model_inputs}
    )

    top_level_config = {
        "plant_config": plant_config,
        "technology_config": tech_config,
        "driver_config": driver_config,
    }
    h2i = H2IntegrateModel(top_level_config)
    h2i.setup()
    h2i.run()

    assert len(h2i.prob.get_val("site.river_resource.discharge")) == 8760


@pytest.mark.unit
def test_custom_model_name_clash(temp_dir, subtests):
    # Path to the original tech_config.yaml and high-level yaml in the example directory
    orig_tech_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml"
    temp_tech_config = temp_dir / "temp_tech_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "01_onshore_steel_mn" / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = temp_dir / "temp_01_onshore_steel_mn.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml")

    # Copy the original tech_config.yaml and high-level yaml to temp files
    shutil.copy(orig_tech_config, temp_tech_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the tech_config YAML content
    tech_config_data = load_tech_yaml(temp_tech_config)

    tech_config_data["technologies"]["electrolyzer"]["cost_model"] = {
        "model": "BasicElectrolyzerCostModel",
        "model_location": "dummy_path",  # path doesn't matter; just that `model_location` exists
    }

    # Save the modified tech_config YAML back
    with temp_tech_config.open("w") as f:
        yaml.safe_dump(tech_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)
        highlevel_data["driver_config"] = driver_config
        highlevel_data["plant_config"] = plant_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["technology_config"] = str(temp_tech_config)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    with subtests.test("custom model name should not match built-in model names"):
        # Assert that a ValueError is raised with the expected message when running the model
        error_msg = (
            r"Custom model or model_location specified for '"
            r"BasicElectrolyzerCostModel', but 'BasicElectrolyzerCostModel' is a built-in "
            r"H2Integrate model\. "
            r"Using built-in model instead is not allowed\. "
            r"If you want to use a custom model, please rename it in your configuration\."
        )
        with pytest.raises(ValueError, match=error_msg):
            H2IntegrateModel(temp_highlevel_yaml)

    with subtests.test(
        "custom models must use different model names for different class definitions"
    ):
        # Load the tech_config YAML content
        tech_config_data = load_tech_yaml(temp_tech_config)

        tech_config_data["technologies"]["electrolyzer"]["cost_model"] = {
            "model": "DummyClass",
            "model_location": "dummy_path",  # path doesn't matter; `model_location` must exist
        }

        tech_config_data["technologies"]["electrolyzer2"] = deepcopy(
            tech_config_data["technologies"]["electrolyzer"]
        )
        tech_config_data["technologies"]["electrolyzer2"]["cost_model"] = {
            "model": "DummyClass",
            "model_location": "dummy_path",  # path doesn't matter; `model_location` must exist
        }
        # Save the modified tech_config YAML back
        with temp_tech_config.open("w") as f:
            yaml.safe_dump(tech_config_data, f)

        # Load the high-level YAML content
        with temp_highlevel_yaml.open() as f:
            highlevel_data = yaml.safe_load(f)

        # Modify the high-level YAML to point to the temp tech_config file
        highlevel_data["technology_config"] = str(temp_tech_config.name)

        # Save the modified high-level YAML back
        with temp_highlevel_yaml.open("w") as f:
            yaml.safe_dump(highlevel_data, f)

        # Assert that a ValueError is raised with the expected message when running the model
        error_msg = (
            r"User has specified two custom models using the same model"
            r"name ('new_electrolyzer_cost'), but with different model classes\. "
            r"Technologies defined with different"
            r"classes must have different technology names\."
        )


@pytest.mark.unit
def test_custom_financial_model_grouping(temp_dir, subtests):
    orig_tech_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml"
    temp_tech_config = temp_dir / "temp_tech_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "01_onshore_steel_mn" / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = temp_dir / "temp_01_onshore_steel_mn.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml")

    # Copy the original tech_config.yaml and high-level yaml to temp files
    shutil.copy(orig_tech_config, temp_tech_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the tech_config YAML content
    tech_config_data = load_tech_yaml(temp_tech_config)

    # Modify the financial_model entry for one of the technologies
    tech_config_data["technologies"]["steel"]["finance_model"]["group"] = "test_financial_group"
    tech_config_data["technologies"]["electrolyzer"].pop("financial_model", None)

    # Save the modified tech_config YAML back
    with temp_tech_config.open("w") as f:
        yaml.safe_dump(tech_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)
        highlevel_data["driver_config"] = driver_config
        highlevel_data["plant_config"] = plant_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["technology_config"] = str(temp_tech_config)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    # Run the model and check that it does not raise an error
    # (assuming custom financial_model is allowed)
    H2IntegrateModel(temp_highlevel_yaml)


# docs fencepost start: DO NOT REMOVE
@pytest.mark.unit
def test_unsupported_simulation_parameters(temp_dir):
    orig_plant_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml"
    temp_plant_config_ntimesteps = temp_dir / "temp_plant_config_ntimesteps.yaml"
    temp_plant_config_dt = temp_dir / "temp_plant_config_dt.yaml"

    shutil.copy(orig_plant_config, temp_plant_config_ntimesteps)
    shutil.copy(orig_plant_config, temp_plant_config_dt)

    # Load the plant_config YAML content
    plant_config_data_ntimesteps = load_plant_yaml(temp_plant_config_ntimesteps)
    plant_config_data_dt = load_plant_yaml(temp_plant_config_dt)
    # docs fencepost end: DO NOT REMOVE

    # Modify the n_timesteps entry for the temp_plant_config_ntimesteps
    plant_config_data_ntimesteps["plant"]["simulation"]["n_timesteps"] = 8759
    # Modify the dt entry for the temp_plant_config_dt
    plant_config_data_dt["plant"]["simulation"]["dt"] = 3601

    # Save the modified plant_configs YAML back
    with temp_plant_config_ntimesteps.open("w") as f:
        yaml.safe_dump(plant_config_data_ntimesteps, f)
    with temp_plant_config_dt.open("w") as f:
        yaml.safe_dump(plant_config_data_dt, f)

    # check that error is thrown when loading config with invalid number of timesteps
    with pytest.raises(ValueError, match="greater than 1-year"):
        load_plant_yaml(plant_config_data_ntimesteps)


@pytest.mark.unit
def test_check_time_step_with_model_bounds_allows_supported_dt():
    class DummyModel:
        _time_step_bounds = (900, 3600)

    model = object.__new__(H2IntegrateModel)
    model.plant_config = {"plant": {"simulation": {"dt": 1800}}}

    model._check_time_step("DummyModel", DummyModel)


@pytest.mark.unit
def test_check_time_step_with_model_bounds_raises_for_unsupported_dt():
    class DummyModel:
        _time_step_bounds = (
            900,
            3600,
        )  # (min, max) time step lengths (in seconds) compatible with this model

    model = object.__new__(H2IntegrateModel)
    model.plant_config = {"plant": {"simulation": {"dt": 7200}}}

    with pytest.raises(
        ValueError,
        match=(
            r"Model DummyModel is compatible with time steps between "
            r"900 \(s\) and 3600 \(s\), but a time step of 7200 \(s\) was specified"
        ),
    ):
        model._check_time_step("DummyModel", DummyModel)


@pytest.mark.unit
def test_technology_connections(temp_dir):
    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml"
    temp_plant_config = temp_dir / "temp_plant_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "01_onshore_steel_mn" / "01_onshore_steel_mn.yaml"
    temp_highlevel_yaml = temp_dir / "temp_01_onshore_steel_mn.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml")

    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the plant_config YAML content
    plant_config_data = load_plant_yaml(temp_plant_config)

    new_connection = (["finance_subgroup_electricity", "steel", ("LCOE", "electricity_cost")],)
    new_tech_interconnections = (
        plant_config_data["technology_interconnections"][0:9]
        + list(new_connection)
        + [plant_config_data["technology_interconnections"][9]]
    )
    plant_config_data["technology_interconnections"] = new_tech_interconnections

    # Save the modified tech_config YAML back
    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)
        highlevel_data["driver_config"] = driver_config
        highlevel_data["technology_config"] = tech_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["plant_config"] = str(temp_plant_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    h2i_model = H2IntegrateModel(temp_highlevel_yaml)
    demand_profile = np.ones(8760) * 720.0
    h2i_model.setup()
    h2i_model.prob.set_val("battery.electricity_set_point", demand_profile, units="MW")
    h2i_model.run()


@pytest.mark.unit
def test_resource_connection_error_missing_connection(temp_dir):
    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = EXAMPLE_DIR / "08_wind_electrolyzer" / "plant_config.yaml"
    temp_plant_config = temp_dir / "temp_plant_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "08_wind_electrolyzer" / "wind_plant_electrolyzer.yaml"
    temp_highlevel_yaml = temp_dir / "temp_08_wind_electrolyzer.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "tech_config.yaml")

    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the plant_config YAML content
    plant_config_data = load_plant_yaml(temp_plant_config)

    # Remove resource to tech connection
    plant_config_data.pop("resource_to_tech_connections")

    # Save the modified tech_config YAML back
    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)
        highlevel_data["driver_config"] = driver_config
        highlevel_data["technology_config"] = tech_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["plant_config"] = str(temp_plant_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    with pytest.raises(ValueError) as excinfo:
        H2IntegrateModel(temp_highlevel_yaml)
        assert "Resource models ['wind_resource'] are not in" in str(excinfo.value)


@pytest.mark.unit
def test_resource_connection_error_missing_resource(temp_dir):
    # Path to the original plant_config.yaml and high-level yaml in the example directory
    orig_plant_config = EXAMPLE_DIR / "08_wind_electrolyzer" / "plant_config.yaml"
    temp_plant_config = temp_dir / "temp_plant_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "08_wind_electrolyzer" / "wind_plant_electrolyzer.yaml"
    temp_highlevel_yaml = temp_dir / "temp_08_wind_electrolyzer.yaml"

    driver_config = load_driver_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "tech_config.yaml")

    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)

    # Load the plant_config YAML content
    plant_config_data = load_plant_yaml(temp_plant_config)

    # Remove resource
    plant_config_data["sites"]["site"]["resources"].pop("wind_resource")

    # Save the modified tech_config YAML back
    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_config_data, f)

    # Load the high-level YAML content
    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)
        highlevel_data["driver_config"] = driver_config
        highlevel_data["technology_config"] = tech_config

    # Modify the high-level YAML to point to the temp tech_config file
    highlevel_data["plant_config"] = str(temp_plant_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    with pytest.raises(ValueError) as excinfo:
        H2IntegrateModel(temp_highlevel_yaml)
    assert "Missing resource(s) are ['site.wind_resource']." in str(excinfo.value)

    # Clean up temporary YAML files
    temp_plant_config.unlink(missing_ok=True)
    temp_highlevel_yaml.unlink(missing_ok=True)


@pytest.mark.unit
def test_no_resource_connection_error_resource_to_multiple_techs(temp_dir):
    # Path to the original plant_config.yaml and high-level yaml in the example directory

    driver_config = load_driver_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "tech_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "08_wind_electrolyzer" / "plant_config.yaml")
    # Add a second wind technology
    wind_tech = tech_config["technologies"]["wind"]
    tech_config["technologies"].update({"wind_plant2": wind_tech})
    resource_to_tech_connections = [
        ["site.wind_resource", "wind", "wind_resource_data"],
        ["site.wind_resource", "wind_plant2", "wind_resource_data"],
    ]
    plant_config["resource_to_tech_connections"] = resource_to_tech_connections
    input_config = {
        "plant_config": plant_config,
        "technology_config": tech_config,
        "driver_config": driver_config,
    }
    h2i_model = H2IntegrateModel(input_config)
    h2i_model.setup()
    # Need to call final_setup to trigger the potential error related to the resource connections
    h2i_model.prob.final_setup()
    assert True


@pytest.mark.unit
def test_reports_turned_off(temp_dir):
    # Path to the original config files in the example directory
    orig_plant_config = EXAMPLE_DIR / "07_run_of_river_plant" / "plant_config.yaml"
    orig_driver_config = EXAMPLE_DIR / "07_run_of_river_plant" / "driver_config.yaml"
    orig_tech_config = EXAMPLE_DIR / "07_run_of_river_plant" / "tech_config.yaml"
    orig_highlevel_yaml = EXAMPLE_DIR / "07_run_of_river_plant" / "07_run_of_river.yaml"
    orig_csv = EXAMPLE_DIR / "07_run_of_river_plant" / "river_data.csv"

    # Create temporary config files
    temp_plant_config = temp_dir / "temp_plant_config.yaml"
    temp_driver_config = temp_dir / "temp_driver_config.yaml"
    temp_tech_config = temp_dir / "temp_tech_config.yaml"
    temp_highlevel_yaml = temp_dir / "temp_07_run_of_river.yaml"
    temp_csv = temp_dir / "river_data.csv"

    # Copy the original config files to temp files
    shutil.copy(orig_highlevel_yaml, temp_highlevel_yaml)
    shutil.copy(orig_plant_config, temp_plant_config)
    shutil.copy(orig_driver_config, temp_driver_config)
    shutil.copy(orig_tech_config, temp_tech_config)
    shutil.copy(orig_csv, temp_csv)

    # Load and modify the driver config to turn off reports
    with temp_driver_config.open() as f:
        driver_data = yaml.safe_load(f)

    if "general" not in driver_data:
        driver_data["general"] = {}
    driver_data["general"]["create_om_reports"] = False

    # Save the modified driver config
    with temp_driver_config.open("w") as f:
        yaml.safe_dump(driver_data, f)

    # Load the high-level YAML content and point to temp config files
    with temp_plant_config.open("r") as f:
        plant_data = yaml.safe_load(f)
        plant_data["sites"]["site"]["resources"]["river_resource"]["resource_parameters"][
            "filename"
        ] = str(temp_csv)

    with temp_plant_config.open("w") as f:
        yaml.safe_dump(plant_data, f)

    with temp_highlevel_yaml.open() as f:
        highlevel_data = yaml.safe_load(f)

    # Modify the high-level YAML to point to the temp config files
    highlevel_data["plant_config"] = str(temp_plant_config.name)
    highlevel_data["driver_config"] = str(temp_driver_config.name)
    highlevel_data["technology_config"] = str(temp_tech_config.name)

    # Save the modified high-level YAML back
    with temp_highlevel_yaml.open("w") as f:
        yaml.safe_dump(highlevel_data, f)

    # Record initial files before running the model
    initial_files = set(Path.cwd().rglob("*"))

    # Run the model
    h2i_model = H2IntegrateModel(temp_highlevel_yaml)
    h2i_model.run()

    # Check that no OpenMDAO report directories were created
    final_files = set(Path.cwd().rglob("*"))
    new_files = final_files - initial_files
    report_dirs = [f for f in new_files if f.is_dir() and "reports" in f.name.lower()]

    # Assert that no report directories were created due to create_om_reports=False
    assert (
        len(report_dirs) == 0
    ), f"Report directories were created despite create_om_reports=False: {report_dirs}"


@pytest.mark.unit
def test_invalid_finance_group_combination(subtests):
    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml")

    invalid_finance_subgroup = {
        "commodity": "steel",
        "commodity_stream": "steel",
        "finance_groups": ["steel", "profast_model"],
        "technologies": ["steel"],
    }

    plant_config["finance_parameters"]["finance_subgroups"].update(
        {"steel_buggy": invalid_finance_subgroup}
    )

    h2i_config = {
        "name": "H2I",
        "system_summary": "",
        "driver_config": driver_config,
        "technology_config": tech_config,
        "plant_config": plant_config,
    }

    with subtests.test("Test invalid finance groups"):
        expected_msg = (
            "Cannot run a tech-specific finance model (['steel']) in the "
            "same finance subgroup as a system-level finance model "
            "(['profast_model']). Please modify the finance_groups in finance "
            "subgroup steel_buggy."
        )

        with pytest.raises(ValueError) as excinfo:
            h2i = H2IntegrateModel(h2i_config)
            h2i.setup()
        assert expected_msg == str(excinfo.value)


@pytest.mark.unit
def test_finance_subgroup_missing_commodity_stream_raises(subtests):
    """A finance subgroup missing ``commodity_stream`` must raise a clear error.

    ``commodity_stream`` is a required field on every finance subgroup; if it
    is omitted the framework must raise ``ValueError`` with a clear message
    rather than letting ``commodity_stream`` remain ``None`` (which would later
    produce ``None.rated_*_production`` connection errors from OpenMDAO).
    """
    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml")

    expected_msg = (
        r"Finance subgroup 'electricity' \(commodity 'electricity'\) is "
        r"missing the required `commodity_stream` field\. Please specify "
        r"which technology's output should be used as the commodity stream "
        r"for this subgroup\."
    )

    scenarios = {
        "no producing tech in subgroup": ["electrolyzer", "h2_storage"],
        "multiple producing techs in subgroup": ["wind", "solar", "battery"],
    }

    for label, technologies in scenarios.items():
        with subtests.test(label):
            plant_config = load_plant_yaml(
                EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml"
            )
            plant_config["finance_parameters"]["finance_subgroups"]["electricity"].pop(
                "commodity_stream", None
            )
            plant_config["finance_parameters"]["finance_subgroups"]["electricity"][
                "technologies"
            ] = technologies

            h2i_config = {
                "name": "H2I",
                "system_summary": "",
                "driver_config": driver_config,
                "technology_config": tech_config,
                "plant_config": plant_config,
            }

            with pytest.raises(ValueError, match=expected_msg):
                H2IntegrateModel(h2i_config)


@pytest.mark.unit
def test_system_order(subtests):
    driver_config = load_driver_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "driver_config.yaml")
    tech_config = load_tech_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "tech_config.yaml")
    plant_config = load_plant_yaml(EXAMPLE_DIR / "01_onshore_steel_mn" / "plant_config.yaml")

    h2i_config = {
        "name": "H2I",
        "system_summary": "",
        "driver_config": driver_config,
        "technology_config": tech_config,
        "plant_config": plant_config,
    }

    h2i = H2IntegrateModel(h2i_config)
    h2i.setup()

    expected_names = [
        "wind",
        "electricity_wind_to_combiner_cable",
        "solar",
        "electricity_solar_to_combiner_cable",
        "combiner",
        "electricity_combiner_to_elec_combiner_cable",
        "electricity_combiner_to_battery_cable",
        "battery",
        "electricity_battery_to_elec_combiner_cable",
        "elec_combiner",
        "electricity_elec_combiner_to_electrolyzer_cable",
        "electrolyzer",
        "hydrogen_electrolyzer_to_h2_combiner_pipe",
        "hydrogen_electrolyzer_to_h2_storage_pipe",
        "h2_storage",
        "hydrogen_h2_storage_to_h2_combiner_pipe",
        "h2_combiner",
        "steel",
        "finance_subgroup_electricity",
        "finance_subgroup_hydrogen",
        "finance_subgroup_steel",
    ]

    names = [sys.name for sys in h2i.model.plant.system_iter(include_self=False, recurse=False)]
    with subtests.test("Test expected names are all present"):
        assert sorted(names) == sorted(expected_names)

    with subtests.test("Test expected names are in the correct order"):
        assert names == expected_names


@pytest.mark.unit
def test_no_sites_entry(temp_dir):
    """Verify that a model can set up and run without a ``sites`` entry in the plant config.

    Uses Example 32 (multivariable streams), whose plant_config intentionally
    omits the ``sites`` key.
    """
    example_folder = EXAMPLE_DIR / "32_multivariable_streams"
    shutil.copytree(example_folder, temp_dir / "32_multivariable_streams", dirs_exist_ok=True)

    os.chdir(temp_dir / "32_multivariable_streams")

    model = H2IntegrateModel(
        temp_dir / "32_multivariable_streams" / "32_multivariable_streams.yaml"
    )
    model.run()

    # Smoke-check: combiner output flow should be the sum of the two producers
    flow_out = model.prob.get_val("gas_combiner.wellhead_gas_mixture:mass_flow_out", units="kg/h")
    assert flow_out.mean() > 0.0

    os.chdir(Path(__file__).parent)


@pytest.mark.unit
def test_create_xdsm_calls_create_xdsm_from_config_default_outfile():
    plant_config = {"technology_interconnections": [("wind", "electrolyzer", "electricity")]}
    model = object.__new__(H2IntegrateModel)
    model.plant_config = plant_config

    with patch.object(h2i_model_module, "create_xdsm_from_config") as mock_fn:
        model.create_xdsm()

    mock_fn.assert_called_once_with(plant_config, output_file="connections_xdsm")


@pytest.mark.unit
def test_create_xdsm_calls_create_xdsm_from_config_custom_outfile():
    plant_config = {"technology_interconnections": [("wind", "electrolyzer", "electricity")]}
    model = object.__new__(H2IntegrateModel)
    model.plant_config = plant_config
    outfile = "my_custom_xdsm"

    with patch.object(h2i_model_module, "create_xdsm_from_config") as mock_fn:
        model.create_xdsm(outfile=outfile)

    mock_fn.assert_called_once_with(plant_config, output_file=outfile)


@pytest.mark.unit
def test_create_xdsm_raises_when_no_interconnections():
    plant_config = {"technology_interconnections": []}
    model = object.__new__(H2IntegrateModel)
    model.plant_config = plant_config

    with patch.object(h2i_model_module, "create_xdsm_from_config") as mock_fn:
        with pytest.raises(ValueError, match="requires technology interconnections"):
            model.create_xdsm()

    mock_fn.assert_not_called()


@pytest.mark.unit
def test_create_xdsm_raises_when_interconnections_key_missing():
    plant_config = {}
    model = object.__new__(H2IntegrateModel)
    model.plant_config = plant_config

    with patch.object(h2i_model_module, "create_xdsm_from_config") as mock_fn:
        with pytest.raises(ValueError, match="requires technology interconnections"):
            model.create_xdsm()

    mock_fn.assert_not_called()


@pytest.mark.unit
def test_create_xdsm_propagates_file_not_found_error():
    plant_config = {"technology_interconnections": [("wind", "electrolyzer", "electricity")]}
    model = object.__new__(H2IntegrateModel)
    model.plant_config = plant_config

    with patch.object(
        h2i_model_module,
        "create_xdsm_from_config",
        side_effect=FileNotFoundError("latex not found"),
    ):
        with pytest.raises(FileNotFoundError, match="latex not found"):
            model.create_xdsm()
