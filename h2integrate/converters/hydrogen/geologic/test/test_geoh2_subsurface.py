import numpy as np
import pytest
import openmdao.api as om

from h2integrate.tools.inflation.inflate import inflate_cpi, inflate_cepci
from h2integrate.converters.hydrogen.geologic.mathur_modified import GeoH2SubsurfaceCostModel
from h2integrate.converters.hydrogen.geologic.templeton_serpentinization import (
    StimulatedGeoH2PerformanceModel,
)


PLANT_LIFE = 20
N_TIMESTEPS = 8760
# Matches the stimulated case in examples/04_geo_h2
STIMULATED_H2_RATE = 155.03934945719536  # kg/h


def make_plant_config(target_dollar_year=2022):
    return {
        "plant": {
            "plant_life": PLANT_LIFE,
            "simulation": {"n_timesteps": N_TIMESTEPS, "dt": 3600},
        },
        "finance_parameters": {
            "cost_adjustment_parameters": {"target_dollar_year": target_dollar_year},
        },
    }


@pytest.fixture
def stimulated_tech_config():
    return {
        "model_inputs": {
            "shared_parameters": {
                "borehole_depth": 4000,
                "well_diameter": "small",
                "well_geometry": "horizontal",
            },
            "performance_parameters": {
                "rock_type": "peridotite",
                "grain_size": 0.001,
                "olivine_phase_vol": 50,
                "olivine_fe_ii_conc": 15,
                "depth_to_formation": 1000,
                "inj_prod_distance": 100,
                "reaction_zone_width": 50,
                "bulk_density": 2700,
                "water_temp": 90,
            },
        }
    }


@pytest.fixture
def subsurface_cost_tech_config():
    return {
        "model_inputs": {
            "shared_parameters": {
                "borehole_depth": 300,
                "well_diameter": "small",
                "well_geometry": "vertical",
            },
            "cost_parameters": {
                "use_cost_curve": False,
                "constant_drill_cost": 1.0e6,
                "test_drill_cost": 500000,
                "permit_fees": 905,
                "acreage": 500,
                "rights_cost": 3,
                "success_chance": 20,
                "fixed_opex": 200000,
                "variable_opex": 0.3,
                "contracting_pct": 20,
                "contingency_pct": 50,
                "preprod_time": 6,
                "as_spent_ratio": 1.1,
            },
        }
    }


def run_component(component_class, plant_config, tech_config, **values):
    prob = om.Problem()
    comp = component_class(plant_config=plant_config, tech_config=tech_config, driver_config={})
    prob.model.add_subsystem("comp", comp, promotes=["*"])
    prob.setup()
    for name, value in values.items():
        prob.set_val(name, value)
    prob.run_model()
    return prob


@pytest.mark.unit
def test_stimulated_geoh2_performance_outputs(subtests, stimulated_tech_config):
    prob = run_component(
        StimulatedGeoH2PerformanceModel, make_plant_config(), stimulated_tech_config
    )
    hydrogen_out = prob.get_val("hydrogen_out", units="kg/h")

    with subtests.test("Hydrogen production is constant and positive"):
        assert np.all(hydrogen_out > 0)
        np.testing.assert_allclose(hydrogen_out, hydrogen_out[0])

    with subtests.test("Wellhead gas and stimulated hydrogen match hydrogen output"):
        np.testing.assert_allclose(prob.get_val("wellhead_gas_out", units="kg/h"), hydrogen_out)
        np.testing.assert_allclose(prob.get_val("hydrogen_out_stim", units="kg/h"), hydrogen_out)

    with subtests.test("Totals and annual production"):
        total = hydrogen_out.sum()
        assert prob.get_val("total_hydrogen_produced", units="kg") == pytest.approx(total)
        assert prob.get_val("total_wellhead_gas_produced", units="kg/year") == pytest.approx(total)
        np.testing.assert_allclose(prob.get_val("annual_hydrogen_produced", units="kg/year"), total)

    with subtests.test("Capacity factor is one for constant production"):
        np.testing.assert_allclose(prob.get_val("capacity_factor"), 1.0)


@pytest.mark.unit
def test_stimulated_geoh2_production_scales_with_reacting_rock(subtests, stimulated_tech_config):
    baseline = run_component(
        StimulatedGeoH2PerformanceModel, make_plant_config(), stimulated_tech_config
    )
    baseline_h2 = baseline.get_val("hydrogen_out", units="kg/h")

    with subtests.test("Doubling the iron (II) content doubles hydrogen production"):
        prob = run_component(
            StimulatedGeoH2PerformanceModel,
            make_plant_config(),
            stimulated_tech_config,
            olivine_fe_ii_conc=30.0,
        )
        np.testing.assert_allclose(prob.get_val("hydrogen_out", units="kg/h"), 2 * baseline_h2)

    with subtests.test("Doubling the reaction zone width doubles hydrogen production"):
        prob = run_component(
            StimulatedGeoH2PerformanceModel,
            make_plant_config(),
            stimulated_tech_config,
            reaction_zone_width=100.0,
        )
        np.testing.assert_allclose(prob.get_val("hydrogen_out", units="kg/h"), 2 * baseline_h2)

    with subtests.test("Water closer to the optimal 260 C reacts faster"):
        prob = run_component(
            StimulatedGeoH2PerformanceModel,
            make_plant_config(),
            stimulated_tech_config,
            water_temp=200.0,
        )
        assert np.all(prob.get_val("hydrogen_out", units="kg/h") > baseline_h2)


@pytest.mark.regression
def test_stimulated_geoh2_performance_value(stimulated_tech_config):
    prob = run_component(
        StimulatedGeoH2PerformanceModel, make_plant_config(), stimulated_tech_config
    )

    assert prob.get_val("hydrogen_out", units="kg/h")[0] == pytest.approx(STIMULATED_H2_RATE)


@pytest.mark.unit
def test_geoh2_subsurface_cost_constant_drill_cost(subtests, subsurface_cost_tech_config):
    total_wellhead_gas = 1.0e6  # kg/year
    prob = run_component(
        GeoH2SubsurfaceCostModel,
        make_plant_config(target_dollar_year=2022),
        subsurface_cost_tech_config,
        total_wellhead_gas_produced=total_wellhead_gas,
    )
    # Costs are in 2022 dollars, so only the constant drill cost (2010 dollars) is inflated
    cost_per_well = 500000 + 905 + 500 * 3
    completion = inflate_cepci(1.0e6, 2010, 2022)
    bare_capex = cost_per_well / 0.20 + completion
    total_plant_cost = bare_capex * 1.20 * 1.50
    total_overnight_cost = total_plant_cost + 200000 * 6 / 12

    with subtests.test("Bare capital cost accounts for unsuccessful test wells"):
        assert prob.get_val("bare_capital_cost", units="USD") == pytest.approx(bare_capex)

    with subtests.test("CapEx applies contracting, contingency, preproduction, and as-spent"):
        assert prob.get_val("CapEx", units="USD") == pytest.approx(total_overnight_cost * 1.1)

    with subtests.test("Fixed and variable OpEx"):
        assert prob.get_val("OpEx", units="USD/year") == pytest.approx(200000)
        np.testing.assert_allclose(
            prob.get_val("VarOpEx", units="USD/year"), 0.3 * total_wellhead_gas
        )

    with subtests.test("Cost year follows the target dollar year"):
        assert prob.get_val("cost_year") == 2022


@pytest.mark.unit
@pytest.mark.parametrize(
    "target_dollar_year,expected_cost_year", [(2005, 2010), (2018, 2018), (2030, 2024)]
)
def test_geoh2_subsurface_cost_year_is_clamped(
    subsurface_cost_tech_config, target_dollar_year, expected_cost_year
):
    prob = run_component(
        GeoH2SubsurfaceCostModel,
        make_plant_config(target_dollar_year=target_dollar_year),
        subsurface_cost_tech_config,
    )

    assert prob.get_val("cost_year") == expected_cost_year
    assert prob.get_val("OpEx", units="USD/year") == pytest.approx(
        inflate_cpi(200000, 2022, expected_cost_year)
    )


@pytest.mark.unit
def test_geoh2_subsurface_cost_curve(subtests, subsurface_cost_tech_config):
    cost_parameters = subsurface_cost_tech_config["model_inputs"]["cost_parameters"]
    cost_parameters["use_cost_curve"] = True
    cost_parameters.pop("constant_drill_cost")
    shared_parameters = subsurface_cost_tech_config["model_inputs"]["shared_parameters"]
    cost_per_successful_well = (500000 + 905 + 500 * 3) / 0.20

    def completion_cost(geometry, diameter, depth):
        shared_parameters.update({"well_geometry": geometry, "well_diameter": diameter})
        prob = run_component(
            GeoH2SubsurfaceCostModel,
            make_plant_config(target_dollar_year=2022),
            subsurface_cost_tech_config,
            borehole_depth=depth,
        )
        return prob.get_val("bare_capital_cost", units="USD")[0] - cost_per_successful_well

    for geometry in ["vertical", "horizontal"]:
        with subtests.test(f"{geometry} large wells cost more than small wells"):
            assert completion_cost(geometry, "large", 3000.0) > completion_cost(
                geometry, "small", 3000.0
            )

        with subtests.test(f"{geometry} drilling cost increases with depth"):
            assert completion_cost(geometry, "small", 4000.0) > completion_cost(
                geometry, "small", 1000.0
            )


@pytest.mark.regression
@pytest.mark.parametrize(
    "geometry,diameter,expected_completion_cost",
    [
        ("vertical", "small", 5674514.270407623),
        ("vertical", "large", 7688273.749162976),
        ("horizontal", "small", 6133736.187186934),
        ("horizontal", "large", 8429032.084494736),
    ],
)
def test_geoh2_subsurface_cost_curve_values(
    subsurface_cost_tech_config, geometry, diameter, expected_completion_cost
):
    """Pin each drilling cost curve so a change to any coefficient is caught."""
    model_inputs = subsurface_cost_tech_config["model_inputs"]
    model_inputs["shared_parameters"].update({"well_geometry": geometry, "well_diameter": diameter})
    model_inputs["cost_parameters"]["use_cost_curve"] = True
    model_inputs["cost_parameters"].pop("constant_drill_cost")
    prob = run_component(
        GeoH2SubsurfaceCostModel,
        make_plant_config(target_dollar_year=2022),
        subsurface_cost_tech_config,
        borehole_depth=3000.0,
    )
    cost_per_successful_well = (500000 + 905 + 500 * 3) / 0.20

    completion_cost = prob.get_val("bare_capital_cost", units="USD")[0] - cost_per_successful_well
    assert completion_cost == pytest.approx(expected_completion_cost, rel=1e-6)


@pytest.mark.unit
def test_geoh2_subsurface_cost_config_errors(subtests, subsurface_cost_tech_config):
    cost_parameters = subsurface_cost_tech_config["model_inputs"]["cost_parameters"]

    with subtests.test("Cost year cannot be set"):
        cost_parameters["cost_year"] = 2020
        with pytest.raises(ValueError, match="cost year cannot be modified"):
            run_component(
                GeoH2SubsurfaceCostModel, make_plant_config(), subsurface_cost_tech_config
            )
        cost_parameters.pop("cost_year")

    with subtests.test("A constant drill cost is required without the cost curve"):
        drill_cost = cost_parameters.pop("constant_drill_cost")
        with pytest.raises(ValueError, match="'constant_drill_cost' must be provided"):
            run_component(
                GeoH2SubsurfaceCostModel, make_plant_config(), subsurface_cost_tech_config
            )
        cost_parameters["constant_drill_cost"] = drill_cost

    with subtests.test("A constant drill cost cannot be combined with the cost curve"):
        cost_parameters["use_cost_curve"] = True
        with pytest.raises(ValueError, match="'constant_drill_cost' should not be provided"):
            run_component(
                GeoH2SubsurfaceCostModel, make_plant_config(), subsurface_cost_tech_config
            )
