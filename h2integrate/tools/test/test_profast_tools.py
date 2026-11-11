from pathlib import Path

import pytest
from pytest import fixture

from h2integrate.core.dict_utils import dict_to_yaml_formatting
from h2integrate.core.file_utils import load_yaml
from h2integrate.tools.profast_tools import (
    run_profast,
    convert_pf_to_dict,
    make_price_breakdown,
    load_profast_from_config,
    create_and_populate_profast,
)
from h2integrate.core.inputs.validation import write_yaml


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


@pytest.mark.unit
def test_load_profast_from_config(profast_config, tmp_path):
    pf = create_and_populate_profast(profast_config)
    sol, _summary, _price_breakdown = run_profast(pf)

    # mirror the formatting used by ProFastLCO when save_profast_config is True
    config_fpath = tmp_path / "profast_config.yaml"
    write_yaml(dict_to_yaml_formatting(convert_pf_to_dict(pf)), config_fpath)

    pf_loaded, results = load_profast_from_config(config_fpath)

    assert pf_loaded is not pf
    assert pytest.approx(results["sol"]["price"], rel=1e-10) == sol["price"]
