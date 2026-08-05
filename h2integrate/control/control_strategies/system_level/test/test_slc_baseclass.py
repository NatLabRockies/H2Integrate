import numpy as np
import pytest
import openmdao.api as om

from h2integrate import EXAMPLE_DIR, H2IntegrateModel
from h2integrate.core.inputs.validation import load_tech_yaml, load_plant_yaml
from h2integrate.control.control_strategies.system_level.system_level_control_base import (
    SystemLevelControlBase,
)


def make_tech_classifiers(tech_list):
    fixed_techs = []
    flexible_techs = ["wind", "solar", "desalination"]
    dispatchable_techs = ["electrolyzer", "haber_bosch", "natural_gas_plant", "grid_buy", "grid"]
    storage_techs = ["battery", "h2_storage", "nh3_storage"]
    feedstock_techs = ["ng_feedstock", "n2_feedstock", "electricity_feedstock", "ocean"]
    classifiers = {k: "flexible" for k in flexible_techs}
    classifiers |= {k: "dispatchable" for k in dispatchable_techs}
    classifiers |= {k: "storage" for k in storage_techs}
    classifiers |= {k: "feedstock" for k in feedstock_techs}
    classifiers |= {k: "fixed" for k in fixed_techs}

    classifiers |= {k: "connector" for k in tech_list if "combiner" in k}
    classifiers |= {k: "connector" for k in tech_list if "splitter" in k}
    classifiers |= {k: "feedstock" for k in tech_list if "feedstock" in k}
    classifiers |= {k: "demand" for k in tech_list if "demand" in k}

    classified_techs = list(set(tech_list) & set(classifiers))
    tech_control_classifiers = {k: classifiers[k] for k in classified_techs}
    return tech_control_classifiers


def make_slc_topology(plant_config, tech_config):
    model = object.__new__(H2IntegrateModel)
    model.slc = True
    # plant_config["system_level_control"].pop("demand_component")
    model.plant_config = plant_config

    tech_control_classifiers = make_tech_classifiers(list(tech_config["technologies"]))
    model.tech_control_classifiers = tech_control_classifiers
    model.technology_config = tech_config
    model.technology_graph = model.create_technology_graph(
        plant_config.get("technology_interconnections", {})
    )
    slc_topology = model._classify_slc_technologies()
    return slc_topology


def make_and_setup_slc_baseclass(plant_config, tech_config) -> SystemLevelControlBase:
    slc_config = make_slc_topology(plant_config, tech_config)
    slc = object.__new__(SystemLevelControlBase)
    # run the start of setup()
    slc.n_timesteps = plant_config["plant"]["simulation"]["n_timesteps"]
    slc.commodity = slc_config["demand_commodity"]
    slc.commodity_rate_units = slc_config.get("demand_commodity_rate_units", None)
    slc.demand_tech = slc_config["demand_tech"]
    slc.storage_techs_to_control = slc_config.get("storage_techs_to_control", {})
    slc.technology_graph = slc_config["technology_graph"]
    slc.fixed_techs = [k for k, v in slc_config["tech_control_classifiers"].items() if v == "fixed"]
    slc.flexible_techs = [
        k for k, v in slc_config["tech_control_classifiers"].items() if v == "flexible"
    ]
    slc.dispatchable_techs = [
        k for k, v in slc_config["tech_control_classifiers"].items() if v == "dispatchable"
    ]
    slc.storage_techs = [
        k for k, v in slc_config["tech_control_classifiers"].items() if v == "storage"
    ]
    slc.feedstock_comps = [
        k for k, v in slc_config["tech_control_classifiers"].items() if v == "feedstock"
    ]

    slc.input_techs = set(
        slc.fixed_techs + slc.flexible_techs + slc.dispatchable_techs + slc.storage_techs
    )

    slc.demand_input_name = f"{slc.commodity}_demand"

    slc.techs_to_commodities = slc_config["tech_to_commodity"]

    slc.multi_commodity_system = (
        True if len({e[-1] for e in slc.techs_to_commodities}) > 1 else False
    )
    return slc


# Test methods in _post_setup_multi_commodity
# _find_converter_techs()
# _make_conversion_factor_recipes()


@pytest.mark.unit
def test_find_converter_techs_fake_system(subtests):
    # Test methods in _post_setup_multi_commodity
    # _find_converter_techs()
    tech_connections = [
        ["ocean", "desalination", "salt_water", ""],
        ["desalination", "electrolyzer", "fresh_water", ""],
        ["wind", "elec_combiner", "electricity", ""],
        ["solar", "elec_combiner", "electricity", ""],
        ["elec_combiner", "battery", "electricity", ""],
        ["battery", "elec_combiner_2", "electricity", ""],
        ["elec_combiner", "elec_combiner_2", "electricity", ""],
        ["elec_combiner_2", "electrolyzer", "electricity", ""],
        ["electrolyzer", "h2_storage", "hydrogen", ""],
        ["electrolyzer", "h2_combiner", "hydrogen", ""],
        ["electrolyzer", "haber_bosch", "oxygen", ""],
        ["electrolyzer", "haber_bosch", "heat", ""],
        ["h2_storage", "h2_combiner", "hydrogen", ""],
        ["h2_combiner", "haber_bosch", "hydrogen", ""],
        ["grid", "haber_bosch", "electricity", ""],
        ["n2_feedstock", "haber_bosch", "nitrogen", ""],
        ["haber_bosch", "nh3_storage", "ammonia", ""],
        ["haber_bosch", "nh3_combiner", "ammonia", ""],
        ["nh3_storage", "nh3_combiner", "ammonia", ""],
        ["nh3_combiner", "nh3_load_demand", "ammonia", ""],
    ]

    example_folder = EXAMPLE_DIR / "35_system_level_control" / "nh3_with_storage"
    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")

    plant_config["technology_interconnections"] = tech_connections
    extra_tech_config_keys = {
        k[0]: {} for k in tech_connections if k[0] not in tech_config["technologies"]
    }
    extra_tech_config_keys |= {
        k[1]: {} for k in tech_connections if k[1] not in tech_config["technologies"]
    }
    tech_config_fake = tech_config["technologies"] | extra_tech_config_keys

    slc = make_and_setup_slc_baseclass(plant_config, {"technologies": tech_config_fake})

    converters, converter_upstreams = slc._find_converter_techs()
    pem_output_cmod = ["hydrogen", "heat", "oxygen"]
    electrolyzer_conversions = [("electricity", "electrolyzer", c) for c in pem_output_cmod]
    electrolyzer_conversions += [("fresh_water", "electrolyzer", c) for c in pem_output_cmod]
    with subtests.test("Converter elements for electrolyzer"):
        assert all(k in converters for k in electrolyzer_conversions)

    hb_conversions = [(c, "haber_bosch", "ammonia") for c in pem_output_cmod]
    with subtests.test("Converter elements for haber_bosch"):
        assert all(k in converters for k in hb_conversions)

    expected_converter_upstreams = {
        ("salt_water", "desalination"): ["ocean"],
        ("hydrogen", "haber_bosch"): ["h2_combiner", "electrolyzer", "h2_storage"],
        ("heat", "haber_bosch"): ["electrolyzer"],
        ("oxygen", "haber_bosch"): ["electrolyzer"],
        ("nitrogen", "haber_bosch"): ["n2_feedstock"],
        ("electricity", "haber_bosch"): ["grid"],
        ("fresh_water", "electrolyzer"): ["desalination"],
        ("electricity", "electrolyzer"): [
            "elec_combiner",
            "elec_combiner_2",
            "battery",
            "solar",
            "wind",
        ],
    }

    mismatched_upstreams = [
        k for k, v in expected_converter_upstreams.items() if set(converter_upstreams[k]) != set(v)
    ]
    with subtests.test("Converter upstreams"):
        assert len(mismatched_upstreams) == 0

    slc._post_setup_multi_commodity()

    with subtests.test("12 distinct conversions"):
        assert len(slc.rename_me_config.converters) == len(converters)
        assert len(converters) == 12

    with subtests.test("9 groups"):
        assert len(slc.rename_me_config.grouped_techs) == 9

    with subtests.test("17 conversion recipes"):
        assert len(slc.rename_me_config.conversion_recipes) == 17

    conversion_to_group_name = {}
    for input_cmod, tech, output_cmod in list(slc.rename_me_config.converters):
        group_name = [
            k[2][1]
            for k in slc.rename_me_config.conversion_recipes
            if k[0] == output_cmod and k[1] == input_cmod
        ]
        conversion_to_group_name[(input_cmod, tech, output_cmod)] = list(set(group_name))[0]

    grouped_tech_in_degrees = dict(slc.rename_me_config.simple_graph.in_degree())
    grouped_tech_out_degrees = dict(slc.rename_me_config.simple_graph.out_degree())
    electrolyzer_in_degs = [
        grouped_tech_in_degrees[conversion_to_group_name[con]] for con in electrolyzer_conversions
    ]
    with subtests.test("electrolyzer in degrees"):
        assert all(k == 2 for k in electrolyzer_in_degs)
    hb_in_degs = [grouped_tech_in_degrees[conversion_to_group_name[con]] for con in hb_conversions]
    with subtests.test("haber bosch in degrees"):
        assert all(k == 5 for k in hb_in_degs)
    multi_output_grouped_techs = [k for k, v in grouped_tech_out_degrees.items() if v > 1]
    electrolyzer_groups = {conversion_to_group_name[con] for con in electrolyzer_conversions}
    with subtests.test("3 electrolyzer groups"):
        assert len(electrolyzer_groups) == 3
    with subtests.test("out degrees are <1 except for electrolyzer upstream"):
        for source_group in multi_output_grouped_techs:
            assert all(
                slc.rename_me_config.simple_graph.has_edge(source_group, dest_group)
                for dest_group in electrolyzer_groups
            )
            assert grouped_tech_out_degrees[source_group] == 3

    recipe_names_long = [
        k
        for k in slc.rename_me_config.conversion_recipes
        if k[0] == "fresh_water" and k[1] == "salt_water"
    ]
    r0_partial = [("ammonia", "nh3_storage", "ammonia"), ("ammonia", "nh3_combiner", "ammonia")]
    r2 = [("salt_water", "desalination", "fresh_water")]
    with subtests.test("desalination recipes"):
        for recipe_name in recipe_names_long:
            recipe = slc.rename_me_config.conversion_recipes[recipe_name]

            cmod_diff = list(set(recipe[0]) - set(r0_partial))
            cmod = cmod_diff[0][0]
            assert cmod in pem_output_cmod
            assert ("fresh_water", "electrolyzer", cmod) in recipe[1]
            assert recipe[2] == r2


@pytest.mark.unit
def test_find_converter_techs_nh3_system(subtests):
    # Test methods in _post_setup_multi_commodity
    # _find_converter_techs()
    example_folder = EXAMPLE_DIR / "35_system_level_control" / "nh3_with_storage"
    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")
    slc = make_and_setup_slc_baseclass(plant_config, tech_config)

    # Test _find_converter_techs()
    converters, converter_upstreams = slc._find_converter_techs()

    expected_converters = {
        ("nitrogen", "haber_bosch", "ammonia"),
        ("electricity", "haber_bosch", "ammonia"),
        ("hydrogen", "haber_bosch", "ammonia"),
        ("electricity", "electrolyzer", "hydrogen"),
    }

    expected_converter_upstreams = {
        ("electricity", "electrolyzer"): {"solar", "battery", "wind"},
        ("hydrogen", "haber_bosch"): {"electrolyzer", "h2_storage"},
        ("electricity", "haber_bosch"): {"electricity_feedstock"},
        ("nitrogen", "haber_bosch"): {"n2_feedstock"},
    }

    with subtests.test("converters"):
        assert converters == expected_converters
    with subtests.test("converter_upstreams"):
        for k, v in expected_converter_upstreams.items():
            input_tech_upstreams = set(converter_upstreams.get(k)) & (
                set(slc.input_techs) | set(slc.feedstock_comps)
            )
            assert input_tech_upstreams == v

    # Test _find_demand_tech_group()
    # non_converter_input_techs_in_group, demand_group = slc._find_demand_tech_group(
    #     converters, converter_upstreams
    # )

    # with subtests.test("non main techs in demand group"):
    #     assert non_converter_input_techs_in_group == ["nh3_storage"]

    # expected_demand_group = {"ammonia-5": {"nh3_combiner", "haber_bosch", "nh3_storage"}}
    # with subtests.test("demand_group"):
    #     assert demand_group == expected_demand_group


@pytest.mark.unit
def test_multi_commodity_post_setup_nh3_system(subtests):
    # Test methods in _post_setup_multi_commodity
    # _find_converter_techs()
    # _make_conversion_factor_recipes()
    example_folder = EXAMPLE_DIR / "35_system_level_control" / "nh3_with_storage"
    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")
    slc_config = make_slc_topology(plant_config, tech_config)

    prob = om.Problem()

    feedstock_techs = [
        k for k, v in slc_config["tech_control_classifiers"].items() if v == "feedstock"
    ]
    feedstock_subsystem_names = []
    for fi, feedstock_tech in enumerate(feedstock_techs):
        feedstock_commodity = [
            e[-1] for e in slc_config["tech_to_commodity"] if e[0] == feedstock_tech
        ]
        feedstock_comp = prob.model.add_subsystem(f"IVC{fi}", om.Group())
        feedstock_comp.add_subsystem(
            "feedstock",
            om.IndepVarComp(
                name=f"{feedstock_tech}_{feedstock_commodity[0]}_out",
                val=np.full(plant_config["plant"]["simulation"]["n_timesteps"], 1e9),
                units="MMBtu/h",
            ),
        )

        feedstock_subsystem_names.append(
            f"IVC{fi}.feedstock.{feedstock_tech}_{feedstock_commodity[0]}_out"
        )

    slc = SystemLevelControlBase(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
        slc_topology=slc_config,
    )
    prob.model.add_subsystem("slc", slc)

    for feedstock_name in feedstock_subsystem_names:
        connection_destination = feedstock_name.split(".")[-1]
        prob.model.connect(feedstock_name, f"slc.{connection_destination}")

    prob.setup()

    # Check converters
    expected_converters = {
        ("nitrogen", "haber_bosch", "ammonia"),
        ("electricity", "haber_bosch", "ammonia"),
        ("hydrogen", "haber_bosch", "ammonia"),
        ("electricity", "electrolyzer", "hydrogen"),
    }

    converters = prob.model.slc.rename_me_config.converters

    with subtests.test("converters"):
        assert converters == expected_converters

    # Check converter_upstreams
    expected_converter_upstreams = {
        ("electricity", "electrolyzer"): {"solar", "battery", "wind"},
        ("hydrogen", "haber_bosch"): {"electrolyzer", "h2_storage"},
        ("electricity", "haber_bosch"): {"electricity_feedstock"},
        ("nitrogen", "haber_bosch"): {"n2_feedstock"},
        # ("ammonia", "nh3_load_demand"): {"haber_bosch", "nh3_storage"},
    }

    converter_upstreams = prob.model.slc.rename_me_config.converter_upstreams
    # with subtests.test("converter upstreams"):
    for k, v in expected_converter_upstreams.items():
        with subtests.test(f"converter upstreams {k}"):
            input_tech_upstreams = set(converter_upstreams.get(k)) & (
                set(slc.input_techs) | set(slc.feedstock_comps)
            )
            assert input_tech_upstreams == v

    # Check simple_graph
    simple_graph = prob.model.slc.rename_me_config.simple_graph
    edges = list(simple_graph.edges(data="commodity"))
    with subtests.test("number of edges"):
        assert len(edges) == 5
    non_numbered_edges = [(k[0].split("-")[0], k[1].split("-")[0], k[2]) for k in edges]
    expected_edges = [
        ("electricity", "hydrogen", "electricity"),
        ("hydrogen", "ammonia", "hydrogen"),
        ("ammonia", "nh3_load_demand", "ammonia"),
        ("nitrogen", "ammonia", "nitrogen"),
        ("electricity", "ammonia", "electricity"),
    ]

    with subtests.test("simple_graph edges"):
        # assert not bool(set(edges) ^ set(expected_edges))
        assert set(non_numbered_edges) == set(expected_edges)

    # Check grouped_techs
    grouped_techs = prob.model.slc.rename_me_config.grouped_techs
    expected_groups = [
        {"solar", "battery", "wind", "combiner", "elec_combiner"},
        {"electrolyzer", "h2_storage", "h2_combiner"},
        {"electricity_feedstock"},
        {"n2_feedstock"},
        {"nh3_combiner", "haber_bosch", "nh3_storage"},
    ]
    failed_groups = []
    for group, techs_in_group in grouped_techs.items():
        if not any(g == set(techs_in_group) for g in expected_groups):
            failed_groups.append(group)
    with subtests.test("Grouped technologies is correct"):
        assert len(failed_groups) == 0

    # Check conversion_recipes
    conversion_recipes_list = prob.model.slc.rename_me_config.conversion_recipes
    conversion_recipes = {}
    for k, v in conversion_recipes_list.items():
        v_as_set = [set(vi) for vi in v]
        conversion_recipes[k] = v_as_set
    demand_group_general = [
        ("ammonia", "nh3_storage", "ammonia"),
        ("ammonia", "nh3_combiner", "ammonia"),
    ]

    n2_nh3_recipe = [("nitrogen", "haber_bosch", "ammonia"), *demand_group_general]
    n2_nh3_recipe_name = [k for k in conversion_recipes if k[0] == "ammonia" and k[1] == "nitrogen"]
    with subtests.test("Nitrogen to Ammonia Recipe"):
        assert conversion_recipes[n2_nh3_recipe_name[0]] == [set(n2_nh3_recipe)]

    electricity_nh3_recipe = [("electricity", "haber_bosch", "ammonia"), *demand_group_general]
    electricity_nh3_recipe_name = [
        k for k in conversion_recipes if k[0] == "ammonia" and k[1] == "electricity"
    ]
    with subtests.test("Electricity to Ammonia Recipe"):
        assert conversion_recipes[electricity_nh3_recipe_name[0]] == [set(electricity_nh3_recipe)]

    h2_nh3_recipe = [("hydrogen", "haber_bosch", "ammonia"), *demand_group_general]
    h2_nh3_recipe_name = [k for k in conversion_recipes if k[0] == "ammonia" and k[1] == "hydrogen"]

    with subtests.test("Hydrogen to Ammonia Recipe"):
        assert conversion_recipes[h2_nh3_recipe_name[0]] == [set(h2_nh3_recipe)]

    h2_elec_subrecipe = {
        ("hydrogen", "h2_storage", "hydrogen"),
        ("electricity", "electrolyzer", "hydrogen"),
        ("hydrogen", "h2_combiner", "hydrogen"),
    }
    h2_elec_recipe = [set(h2_nh3_recipe), h2_elec_subrecipe]

    h2_elec_recipe_name = [
        k for k in conversion_recipes if k[0] == "hydrogen" and k[1] == "electricity"
    ]
    with subtests.test("Electricity for Hydrogen Recipe"):
        assert conversion_recipes[h2_elec_recipe_name[0]] == h2_elec_recipe

    with subtests.test("4 recipes"):
        assert len(conversion_recipes) == 4

    # Check non_converter_conversion_factor_keys
    non_converter_keys = prob.model.slc.rename_me_config.non_converter_conversion_factor_keys
    non_converter_techs = [k[1] for k in non_converter_keys]
    expected_non_converter_techs = [
        "nh3_storage",
        "battery",
        "n2_feedstock",
        "wind",
        "electricity_feedstock",
        "solar",
        "h2_storage",
        "elec_combiner",
        "combiner",
        "h2_combiner",
        "nh3_combiner",
    ]
    with subtests.test("Non converter techs"):
        assert set(non_converter_techs) == set(expected_non_converter_techs)
    with subtests.test("wind key"):
        assert ("electricity", "wind", "electricity") in non_converter_keys
    with subtests.test("n2_feedstock key"):
        assert ("nitrogen", "n2_feedstock", "nitrogen") in non_converter_keys
    with subtests.test("h2_combiner key"):
        assert ("hydrogen", "h2_combiner", "hydrogen") in non_converter_keys
    with subtests.test("nh3_storage key"):
        assert ("ammonia", "nh3_storage", "ammonia") in non_converter_keys

    converter_tech_names = prob.model.slc.rename_me_config.converter_tech_names
    with subtests.test("Converter tech names"):
        assert converter_tech_names == {"haber_bosch", "electrolyzer"}


# Test methods used by Demand Following
# `get_converter_capacity_conversion_ratio`
# `get_converter_conversion_ratio`
# `_get_conversion_from_recipe`
# `_get_techs_to_demand_from_recipe`


@pytest.mark.unit
def test_multi_commodity_conversion_factor_nh3_system(subtests):
    # Test methods available in SLC baseclass that are not used directly within SLC baseclass

    # --- Same setup as ``test_multi_commodity_post_setup_nh3_system`` ---

    example_folder = EXAMPLE_DIR / "35_system_level_control" / "nh3_with_storage"
    plant_config = load_plant_yaml(example_folder / "plant_config.yaml")
    tech_config = load_tech_yaml(example_folder / "tech_config.yaml")
    slc_config = make_slc_topology(plant_config, tech_config)

    prob = om.Problem()

    feedstock_techs = [
        k for k, v in slc_config["tech_control_classifiers"].items() if v == "feedstock"
    ]
    feedstock_subsystem_names = []
    for fi, feedstock_tech in enumerate(feedstock_techs):
        feedstock_commodity = [
            e[-1] for e in slc_config["tech_to_commodity"] if e[0] == feedstock_tech
        ]
        feedstock_comp = prob.model.add_subsystem(f"IVC{fi}", om.Group())
        feedstock_comp.add_subsystem(
            "feedstock",
            om.IndepVarComp(
                name=f"{feedstock_tech}_{feedstock_commodity[0]}_out",
                val=np.full(plant_config["plant"]["simulation"]["n_timesteps"], 1e9),
                units="MMBtu/h",
            ),
        )

        feedstock_subsystem_names.append(
            f"IVC{fi}.feedstock.{feedstock_tech}_{feedstock_commodity[0]}_out"
        )

    slc = SystemLevelControlBase(
        plant_config=plant_config,
        tech_config=tech_config,
        driver_config={},
        slc_topology=slc_config,
    )
    prob.model.add_subsystem("slc", slc)

    for feedstock_name in feedstock_subsystem_names:
        connection_destination = feedstock_name.split(".")[-1]
        prob.model.connect(feedstock_name, f"slc.{connection_destination}")

    prob.setup()
    # --------------------------- End of setup ---------------------------
    h2_storage_profile = np.tile(
        np.concatenate([np.arange(-5.0, 6.0, 1), np.arange(6.0, -5, -1)]), 399
    )[:8760]
    fake_inputs = {
        "wind_rated_electricity_production": np.array([30.0]),
        "wind_electricity_out": np.full(8760, 15.0),
        "solar_rated_electricity_production": np.array([25.0]),
        "solar_electricity_out": np.full(8760, 20.0),
        "battery_rated_electricity_production": np.array([16.0]),
        "battery_electricity_out": np.zeros(8760),
        "electrolyzer_rated_hydrogen_production": np.array([71.0]),
        "electrolyzer_hydrogen_out": np.full(8760, 39.0),
        "h2_storage_rated_hydrogen_production": np.array([14.0]),
        "h2_storage_hydrogen_out": h2_storage_profile,
        "haber_bosch_rated_ammonia_production": np.array([50.0]),
        "haber_bosch_ammonia_out": np.full(8760, 40),
        "nh3_storage_rated_ammonia_production": np.array([4.0]),
        "nh3_storage_ammonia_out": np.tile(np.array([-1, 1]), 4380),
        "n2_feedstock_nitrogen_out": np.full(8760, 2.5),
        "electricity_feedstock_electricity_out": np.full(8760, 13.0),
    }

    # Test `get_converter_capacity_conversion_ratio` and `get_converter_conversion_ratio`
    # Electricity to hydrogen
    elec_per_h2_ratio = prob.model.slc.get_converter_conversion_ratio(
        fake_inputs, "electricity", "hydrogen", "electrolyzer", ["battery", "wind", "solar"]
    )
    elec_per_h2_capac_ratio = prob.model.slc.get_converter_capacity_conversion_ratio(
        fake_inputs, "electricity", "hydrogen", "electrolyzer", ["battery", "wind", "solar"]
    )
    elec_capac = 30.0 + 25.0 + 16.0
    elec_gen = 15.0 + 20.0
    with subtests.test("Electricity/Hydrogen conversion ratio"):
        assert pytest.approx(elec_gen / 39.0, rel=1e-6) == elec_per_h2_ratio.mean()
    with subtests.test("Electricity/Hydrogen capacity ratio"):
        assert pytest.approx(elec_capac / 71.0, rel=1e-6) == elec_per_h2_capac_ratio

    # Hydrogen to ammonia
    h2_per_nh3_ratio = prob.model.slc.get_converter_conversion_ratio(
        fake_inputs, "hydrogen", "ammonia", "haber_bosch", ["electrolyzer", "h2_storage"]
    )
    h2_per_nh3_capac_ratio = prob.model.slc.get_converter_capacity_conversion_ratio(
        fake_inputs, "hydrogen", "ammonia", "haber_bosch", ["electrolyzer", "h2_storage"]
    )
    h2_capac = 71.0 + 14.0
    h2_gen = h2_storage_profile + np.full(8760, 39.0)
    with subtests.test("Hydrogen/Ammonia conversion ratio"):
        assert pytest.approx((h2_gen / 40).mean(), rel=1e-6) == h2_per_nh3_ratio.mean()
    with subtests.test("Hydrogen/Ammonia capacity ratio"):
        assert pytest.approx(h2_capac / 50.0, rel=1e-6) == h2_per_nh3_capac_ratio

    # Nitrogen to ammonia
    n2_per_nh3_ratio = prob.model.slc.get_converter_conversion_ratio(
        fake_inputs, "nitrogen", "ammonia", "haber_bosch", ["n2_feedstock"]
    )
    n2_per_nh3_capac_ratio = prob.model.slc.get_converter_capacity_conversion_ratio(
        fake_inputs, "nitrogen", "ammonia", "haber_bosch", ["n2_feedstock"]
    )
    with subtests.test("Nitrogen/Ammonia conversion ratio"):
        assert pytest.approx(2.5 / 40, rel=1e-6) == n2_per_nh3_ratio.mean()
    with subtests.test("Nitrogen/Ammonia capacity ratio"):
        assert pytest.approx(2.5 / 50.0, rel=1e-6) == n2_per_nh3_capac_ratio

    # Electricity to ammonia
    elec_per_nh3_ratio = prob.model.slc.get_converter_conversion_ratio(
        fake_inputs, "electricity", "ammonia", "haber_bosch", ["electricity_feedstock"]
    )
    elec_per_nh3_capac_ratio = prob.model.slc.get_converter_capacity_conversion_ratio(
        fake_inputs, "electricity", "ammonia", "haber_bosch", ["electricity_feedstock"]
    )
    with subtests.test("Electricity/Ammonia conversion ratio"):
        assert pytest.approx(13.0 / 40, rel=1e-6) == elec_per_nh3_ratio.mean()
    with subtests.test("Electricity/Ammonia capacity ratio"):
        assert pytest.approx(13.0 / 50.0, rel=1e-6) == elec_per_nh3_capac_ratio

    # Test `_get_conversion_from_recipe` and `_get_techs_to_demand_from_recipe`
    conversion_factors = {
        ("electricity", "electrolyzer", "hydrogen"): elec_gen / 39.0,
        ("hydrogen", "haber_bosch", "ammonia"): (h2_gen / 40).mean(),
        ("nitrogen", "haber_bosch", "ammonia"): 2.5 / 40,
        ("electricity", "haber_bosch", "ammonia"): 13.0 / 40,
    }
    non_converter_keys = prob.model.slc.rename_me_config.non_converter_conversion_factor_keys
    non_converter_factor = 1.0
    non_converter_conversion_factors = dict(
        zip(non_converter_keys, [non_converter_factor] * len(non_converter_keys))
    )
    all_conversion_factors = conversion_factors | non_converter_conversion_factors

    conversion_recipes = prob.model.slc.rename_me_config.conversion_recipes

    # Nitrogen/Ammonia
    n2_recipe_name = [k for k in conversion_recipes if k[0] == "ammonia" and k[1] == "nitrogen"][0]
    # n2_recipe_name = ("ammonia", "nitrogen", "ammonia-5")
    with subtests.test("Nitrogen/Ammonia Conversion Factor"):
        conversion_factor = prob.model.slc._get_conversion_from_recipe(
            all_conversion_factors, conversion_recipes[n2_recipe_name]
        )
        assert pytest.approx(2.5 / 40.0, rel=1e-6) == conversion_factor
    with subtests.test("Nitrogen/Ammonia Techs"):
        techs_to_demand = prob.model.slc._get_techs_to_demand_from_recipe(n2_recipe_name)
        assert ["n2_feedstock"] == techs_to_demand

    # Electricity/Ammonia
    elec_recipe_name = [
        k for k in conversion_recipes if k[0] == "ammonia" and k[1] == "electricity"
    ][0]
    # elec_recipe_name = ("ammonia", "electricity", "ammonia-5")
    with subtests.test("Electricity/Ammonia Conversion Factor"):
        conversion_factor = prob.model.slc._get_conversion_from_recipe(
            all_conversion_factors, conversion_recipes[elec_recipe_name]
        )
        assert pytest.approx(13.0 / 40.0, rel=1e-6) == conversion_factor
    with subtests.test("Electricity/Ammonia Techs"):
        techs_to_demand = prob.model.slc._get_techs_to_demand_from_recipe(elec_recipe_name)
        assert ["electricity_feedstock"] == techs_to_demand

    # Hydrogen/Ammonia
    h2_recipe_name = [k for k in conversion_recipes if k[0] == "ammonia" and k[1] == "hydrogen"][0]
    # h2_recipe_name = ("ammonia", "hydrogen", "ammonia-5")
    with subtests.test("Hydrogen/Ammonia Conversion Factor"):
        conversion_factor = prob.model.slc._get_conversion_from_recipe(
            all_conversion_factors, conversion_recipes[h2_recipe_name]
        )
        assert pytest.approx((h2_gen / 40).mean(), rel=1e-6) == conversion_factor

    with subtests.test("Hydrogen/Ammonia Techs"):
        techs_to_demand = prob.model.slc._get_techs_to_demand_from_recipe(h2_recipe_name)
        expected_techs = ["h2_storage", "electrolyzer", "h2_combiner"]
        assert set(expected_techs) == set(techs_to_demand)

    # Electricity/Hydrogen/Ammonia
    eh2_recipe_name = [
        k for k in conversion_recipes if k[0] == "hydrogen" and k[1] == "electricity"
    ][0]
    # eh2_recipe_name = ("hydrogen", "electricity", "hydrogen-1")
    with subtests.test("Electricity/Hydrogen/Ammonia Conversion Factor"):
        conversion_factor = prob.model.slc._get_conversion_from_recipe(
            all_conversion_factors, conversion_recipes[eh2_recipe_name]
        )
        expected_conversion_factor = (h2_gen / 40).mean() * (elec_gen / 39.0)
        assert pytest.approx(expected_conversion_factor, rel=1e-6) == conversion_factor
    with subtests.test("Electricity/Hydrogen/Ammonia Techs"):
        techs_to_demand = prob.model.slc._get_techs_to_demand_from_recipe(eh2_recipe_name)
        expected_techs = ["battery", "wind", "solar", "combiner", "elec_combiner"]
        assert set(expected_techs) == set(techs_to_demand)
