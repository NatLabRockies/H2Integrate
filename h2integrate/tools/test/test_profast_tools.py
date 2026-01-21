from pathlib import Path

import pytest
from pytest import fixture
from hopp.utilities.utilities import load_yaml

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


def test_lco_breakdown(profast_config, subtests):
    pf = create_and_populate_profast(profast_config)
    sol, summary, price_breakdown = run_profast(pf)
    full_price_breakdown, lco_check = make_price_breakdown(price_breakdown, profast_config)

    lcoe_initial = float(sol["price"] * 1e3)

    lco_from_breakdown = lco_check * 1e3
    with subtests.test("Breakdown LCOE matches actual LCOE"):
        assert pytest.approx(lco_from_breakdown, rel=1e-6) == lcoe_initial

    with subtests.test(
        "Breakdown LCOE with config created from profast object matches actual LCOE"
    ):
        pf_config_dict = convert_pf_to_dict(pf)
        full_price_breakdown, lco_check = make_price_breakdown(price_breakdown, pf_config_dict)

        assert pytest.approx(lco_check * 1e3, rel=1e-6) == lcoe_initial
