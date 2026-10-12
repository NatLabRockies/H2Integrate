from pathlib import Path

import pytest
from pytest import fixture

from h2integrate.core.file_utils import load_yaml
from h2integrate.tools.profast_tools import (
    run_profast,
    convert_pf_to_dict,
    make_price_breakdown,
    create_and_populate_profast,
)


@fixture
def profast_config():
    config_fpath = Path(__file__).parent / "profast_config.yaml"
    pf_config = load_yaml(config_fpath)

    return pf_config


@pytest.mark.regression
def test_lco_breakdown(profast_config, subtests):
    pf = create_and_populate_profast(profast_config)
    sol, _summary, price_breakdown = run_profast(pf)
    _full_price_breakdown, lco_check = make_price_breakdown(price_breakdown, profast_config)

    lcoe_initial = float(sol["price"] * 1e3)

    lco_from_breakdown = lco_check * 1e3
    with subtests.test("Breakdown LCOE matches actual LCOE"):
        assert pytest.approx(lco_from_breakdown, rel=1e-6) == lcoe_initial

    with subtests.test(
        "Breakdown LCOE with config created from profast object matches actual LCOE"
    ):
        pf_config_dict = convert_pf_to_dict(pf)
        _full_price_breakdown, lco_check = make_price_breakdown(price_breakdown, pf_config_dict)

        assert pytest.approx(lco_check * 1e3, rel=1e-6) == lcoe_initial


@pytest.mark.regression
def test_lco_breakdown_item_attribution(profast_config, subtests):
    # Zero-cost feedstock sorts before the fixed cost of the same tech in ProFAST's breakdown
    ng_feedstock = profast_config["feedstocks"]["ng_feedstock_feedstock"]
    profast_config["feedstocks"]["wind_variable_opex"] = {
        **ng_feedstock,
        "name": "wind_variable_opex",
        "cost": dict.fromkeys(ng_feedstock["cost"], 0.0),
    }
    pf = create_and_populate_profast(profast_config)
    sol, _summary, price_breakdown = run_profast(pf)
    breakdown, lco_check = make_price_breakdown(price_breakdown, profast_config)
    npv = price_breakdown.set_index(["Type", "Name"])["NPV"]

    with subtests.test("Fixed OpEx matches its ProFAST row"):
        wind_opex = npv["Operating expenses", "wind"]
        assert wind_opex > 0
        assert breakdown["LCOE: wind Fixed OpEx ($/kWh)"] == pytest.approx(wind_opex)

    with subtests.test("Variable OpEx matches its ProFAST row"):
        assert breakdown["LCOE: wind Variable OpEx ($/kWh)"] == pytest.approx(0.0)

    with subtests.test("Feedstock matches its ProFAST row"):
        ng_npv = npv["Operating expenses", "ng_feedstock_feedstock"]
        assert ng_npv > 0
        assert breakdown["LCOE: ng_feedstock Feedstock ($/kWh)"] == pytest.approx(ng_npv)

    with subtests.test("Breakdown total matches price"):
        assert lco_check == pytest.approx(sol["price"], rel=1e-6)


@pytest.mark.unit
def test_lco_breakdown_rejects_shared_fixed_cost_and_feedstock_names(profast_config):
    profast_config["feedstocks"]["wind"] = profast_config["feedstocks"]["ng_feedstock_feedstock"]

    with pytest.raises(ValueError, match="unique names"):
        make_price_breakdown(None, profast_config)
