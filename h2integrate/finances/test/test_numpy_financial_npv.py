import pytest
import openmdao.api as om
from pytest import fixture

from h2integrate.finances.numpy_financial_npv import (
    NumpyFinancialNPV,
    NumpyFinancialNPVFinanceConfig,
)


@fixture
def npv_finance_inputs():
    npv_dict = {
        "real_discount_rate": 0.09,
        "commodity_sell_price": 0.04,
        "commodity_sell_price_units": "USD/(kW*h)",
        "save_cost_breakdown": False,
        "save_npv_breakdown": False,
        "cost_breakdown_file_description": False,
    }
    return npv_dict


@fixture
def fake_filtered_tech_config():
    tech_config = {
        "wind": {"model_inputs": {}},
        "solar": {"model_inputs": {}},
        "battery": {"model_inputs": {}},
        "natural_gas": {"model_inputs": {}},
    }
    return tech_config


@fixture
def fake_cost_dict():
    fake_costs = {
        "capex_adjusted_wind": 950054634.1,
        "opex_adjusted_wind": 21093892.68,
        "varopex_adjusted_wind": [0.0] * 30,
        "capex_adjusted_solar": 6561339.6,
        "opex_adjusted_solar": 88372.77,
        "varopex_adjusted_solar": [0.0] * 30,
        "capex_adjusted_battery": 3402926,
        "opex_adjusted_battery": 779.27,
        "varopex_adjusted_battery": [0.0] * 30,
        "capex_adjusted_natural_gas": 1170731708.0,
        "opex_adjusted_natural_gas": 12783853.58,
        "varopex_adjusted_natural_gas": [65458026.9] * 30,
    }
    return fake_costs


@pytest.mark.regression
def test_simple_npv(npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests):
    mean_hourly_production = 500000.0
    prob = om.Problem()
    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": npv_finance_inputs},
    }
    pf = NumpyFinancialNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1",
    )

    ivc = om.IndepVarComp()
    ivc.add_output("rated_electricity_production", mean_hourly_production, units="kW")
    ivc.add_output("capacity_factor", [1.0] * 30, units="unitless")

    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("npv", pf, promotes=["*"])
    prob.setup()

    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"npv.{variable}", cost, units=units)

    prob.run_model()

    with subtests.test("Sell price"):
        assert (
            pytest.approx(
                prob.get_val("npv.sell_price_electricity_no1", units="USD/(kW*h)"), rel=1e-6
            )
            == npv_finance_inputs["commodity_sell_price"]
        )

    with subtests.test("NPV"):
        assert (
            pytest.approx(prob.get_val("npv.NPV_electricity_no1", units="USD")[0], rel=1e-6)
            == -1352263704.120
        )


@pytest.mark.regression
def test_simple_npv_positive(
    npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests
):
    mean_hourly_production = 500000.0
    prob = om.Problem()

    # Increase commodity sell price to get positive NPV
    npv_finance_inputs_positive = npv_finance_inputs.copy()
    npv_finance_inputs_positive["commodity_sell_price"] = 0.15

    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": npv_finance_inputs_positive},
    }
    pf = NumpyFinancialNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1",
    )

    ivc = om.IndepVarComp()
    ivc.add_output("rated_electricity_production", mean_hourly_production, units="kW")
    ivc.add_output("capacity_factor", [1.0] * 30, units="unitless")

    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("npv", pf, promotes=["*"])
    prob.setup()

    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"npv.{variable}", cost, units=units)

    prob.run_model()

    with subtests.test("Sell price"):
        assert (
            pytest.approx(
                prob.get_val("npv.sell_price_electricity_no1", units="USD/(kW*h)"), rel=1e-6
            )
            == npv_finance_inputs_positive["commodity_sell_price"]
        )

    with subtests.test("NPV positive"):
        npv_value = prob.get_val("npv.NPV_electricity_no1", units="USD")[0]
        assert pytest.approx(npv_value, rel=1e-6) == 3597582813.8071656


def _build_npv_problem(npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict):
    """Build and run an NPV problem with the given finance inputs."""
    mean_hourly_production = 500000.0
    prob = om.Problem()

    plant_config = {
        "plant": {
            "plant_life": 30,
        },
        "finance_parameters": {"model_inputs": npv_finance_inputs},
    }
    pf = NumpyFinancialNPV(
        driver_config={},
        plant_config=plant_config,
        tech_config=fake_filtered_tech_config,
        commodity_type="electricity",
        description="no1",
    )

    ivc = om.IndepVarComp()
    ivc.add_output("rated_electricity_production", mean_hourly_production, units="kW")
    ivc.add_output("capacity_factor", [1.0] * 30, units="unitless")

    prob.model.add_subsystem("ivc", ivc, promotes=["*"])
    prob.model.add_subsystem("npv", pf, promotes=["*"])
    prob.setup()

    for variable, cost in fake_cost_dict.items():
        units = "USD" if "capex" in variable else "USD/year"
        prob.set_val(f"npv.{variable}", cost, units=units)

    prob.run_model()
    return prob


@pytest.mark.unit
def test_inflation_rate_defaults_to_zero(
    npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests
):
    """Omitting inflation_rate should reproduce the baseline NPV (nominal-rate behavior)."""
    inputs_no_inflation = npv_finance_inputs.copy()
    inputs_with_zero_inflation = npv_finance_inputs.copy()
    inputs_with_zero_inflation["inflation_rate"] = 0.0

    prob_default = _build_npv_problem(
        inputs_no_inflation, fake_filtered_tech_config, fake_cost_dict
    )
    prob_explicit_zero = _build_npv_problem(
        inputs_with_zero_inflation, fake_filtered_tech_config, fake_cost_dict
    )

    npv_default = prob_default.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_explicit_zero = prob_explicit_zero.get_val("npv.NPV_electricity_no1", units="USD")[0]

    with subtests.test("Default inflation_rate matches baseline NPV"):
        assert pytest.approx(npv_default, rel=1e-6) == -1352263704.120

    with subtests.test("Explicit inflation_rate=0 matches default"):
        assert pytest.approx(npv_explicit_zero, rel=1e-12) == npv_default


@pytest.mark.unit
def test_inflation_rate_combines_via_fisher_equation(
    npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests
):
    """Real and inflation rates should combine via the Fisher equation:
    (1 + r_nominal) = (1 + r_real) * (1 + inflation), matching ProFAST."""
    # Real discount rate 0.05 + inflation 0.04 should give the same NPV as a
    # nominal rate of (1.05 * 1.04 - 1) = 0.092, NOT 0.09 (the additive form).
    nominal_inputs = npv_finance_inputs.copy()
    nominal_inputs["real_discount_rate"] = 1.05 * 1.04 - 1.0  # 0.092

    split_inputs = npv_finance_inputs.copy()
    split_inputs["real_discount_rate"] = 0.05
    split_inputs["inflation_rate"] = 0.04

    inflation_only_inputs = npv_finance_inputs.copy()
    inflation_only_inputs["real_discount_rate"] = 0.0
    inflation_only_inputs["inflation_rate"] = 0.09

    inflation_only_nominal_inputs = npv_finance_inputs.copy()
    inflation_only_nominal_inputs["real_discount_rate"] = 0.09

    prob_nominal = _build_npv_problem(nominal_inputs, fake_filtered_tech_config, fake_cost_dict)
    prob_split = _build_npv_problem(split_inputs, fake_filtered_tech_config, fake_cost_dict)
    prob_inflation_only = _build_npv_problem(
        inflation_only_inputs, fake_filtered_tech_config, fake_cost_dict
    )
    prob_inflation_only_nominal = _build_npv_problem(
        inflation_only_nominal_inputs, fake_filtered_tech_config, fake_cost_dict
    )

    npv_nominal = prob_nominal.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_split = prob_split.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_inflation_only = prob_inflation_only.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_inflation_only_nominal = prob_inflation_only_nominal.get_val(
        "npv.NPV_electricity_no1", units="USD"
    )[0]

    with subtests.test("Real + inflation matches Fisher-equivalent nominal"):
        assert pytest.approx(npv_split, rel=1e-12) == npv_nominal

    with subtests.test("Inflation-only matches equivalent nominal (real=0)"):
        # With real_discount_rate=0, (1+0)*(1+pi)-1 = pi, so this should match a
        # nominal rate equal to the inflation rate exactly.
        assert pytest.approx(npv_inflation_only, rel=1e-12) == npv_inflation_only_nominal


@pytest.mark.unit
def test_inflation_rate_validator_rejects_out_of_range():
    """inflation_rate must be in [0, 1]."""
    with pytest.raises(ValueError, match="inflation_rate"):
        NumpyFinancialNPVFinanceConfig.from_dict(
            {
                "plant_life": 30,
                "real_discount_rate": 0.05,
                "inflation_rate": -0.01,
                "commodity_sell_price_units": "USD/(kW*h)",
            }
        )

    with pytest.raises(ValueError, match="inflation_rate"):
        NumpyFinancialNPVFinanceConfig.from_dict(
            {
                "plant_life": 30,
                "real_discount_rate": 0.05,
                "inflation_rate": 1.5,
                "commodity_sell_price_units": "USD/(kW*h)",
            }
        )


def _make_component(**overrides):
    """Build a NumpyFinancialNPV component with a config from the given overrides.

    The component is not run through OpenMDAO setup; only ``config`` is populated so
    that the ``_real_to_nominal_rate`` and ``_compute_wacc`` helper methods can be
    exercised in isolation.
    """
    params = {
        "plant_life": 30,
        "real_discount_rate": 0.09,
        "commodity_sell_price_units": "USD/(kW*h)",
    }
    params.update(overrides)

    pf = NumpyFinancialNPV(
        driver_config={},
        plant_config={"plant": {"plant_life": 30}, "finance_parameters": {"model_inputs": {}}},
        tech_config={},
        commodity_type="electricity",
    )
    pf.config = NumpyFinancialNPVFinanceConfig.from_dict(params)
    return pf


@pytest.mark.unit
def test_real_to_nominal_rate(subtests):
    """_real_to_nominal_rate applies the Fisher equation, and is a no-op at zero inflation."""
    with subtests.test("Zero inflation returns the real rate unchanged"):
        pf = _make_component(real_discount_rate=0.07, inflation_rate=0.0)
        assert pf._real_to_nominal_rate(0.07) == pytest.approx(0.07, rel=1e-12)

    with subtests.test("Nonzero inflation combines via Fisher equation"):
        pf = _make_component(real_discount_rate=0.05, inflation_rate=0.04)
        expected = 1.05 * 1.04 - 1.0
        assert pf._real_to_nominal_rate(0.05) == pytest.approx(expected, rel=1e-12)

    with subtests.test("Zero real rate returns the inflation rate"):
        pf = _make_component(real_discount_rate=0.0, inflation_rate=0.09)
        assert pf._real_to_nominal_rate(0.0) == pytest.approx(0.09, rel=1e-12)


@pytest.mark.unit
def test_compute_wacc(subtests):
    """_compute_wacc weights equity/debt rates and applies the Fisher conversion (pre-tax)."""
    with subtests.test("Zero debt/equity reduces WACC to the equity rate"):
        pf = _make_component(real_discount_rate=0.09, debt_equity_ratio=0.0)
        assert pf._compute_wacc() == pytest.approx(0.09, rel=1e-12)

    with subtests.test("Debt and debt/equity combine into the pre-tax WACC"):
        pf = _make_component(
            real_discount_rate=0.10,
            debt_rate=0.05,
            debt_equity_ratio=1.0,
        )
        # equity_weight = debt_weight = 0.5 for D/E = 1.0
        # WACC = 0.5 * 0.10 + 0.5 * 0.05 = 0.05 + 0.025 = 0.075
        assert pf._compute_wacc() == pytest.approx(0.075, rel=1e-12)

    with subtests.test("Inflation is applied to both rates before weighting"):
        pf = _make_component(
            real_discount_rate=0.10,
            debt_rate=0.05,
            debt_equity_ratio=1.0,
            inflation_rate=0.03,
        )
        nominal_equity = 1.10 * 1.03 - 1.0
        nominal_debt = 1.05 * 1.03 - 1.0
        expected = 0.5 * nominal_equity + 0.5 * nominal_debt
        assert pf._compute_wacc() == pytest.approx(expected, rel=1e-12)

    with subtests.test("Zero debt/equity with inflation reduces WACC to the nominal equity rate"):
        pf = _make_component(real_discount_rate=0.09, debt_equity_ratio=0.0, inflation_rate=0.02)
        assert pf._compute_wacc() == pytest.approx(1.09 * 1.02 - 1.0, rel=1e-12)


@pytest.mark.unit
def test_wacc_discount_matches_equivalent_single_rate(
    npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests
):
    """NPV computed from WACC inputs should match a single-rate config equal to that WACC."""
    wacc_inputs = npv_finance_inputs.copy()
    wacc_inputs["real_discount_rate"] = 0.10
    wacc_inputs["debt_rate"] = 0.05
    wacc_inputs["debt_equity_ratio"] = 1.0

    # WACC = 0.5 * 0.10 + 0.5 * 0.05 = 0.075
    equivalent_inputs = npv_finance_inputs.copy()
    equivalent_inputs["real_discount_rate"] = 0.075

    prob_wacc = _build_npv_problem(wacc_inputs, fake_filtered_tech_config, fake_cost_dict)
    prob_equivalent = _build_npv_problem(
        equivalent_inputs, fake_filtered_tech_config, fake_cost_dict
    )

    npv_wacc = prob_wacc.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_equivalent = prob_equivalent.get_val("npv.NPV_electricity_no1", units="USD")[0]

    with subtests.test("WACC-based NPV matches equivalent single-rate NPV"):
        assert pytest.approx(npv_wacc, rel=1e-12) == npv_equivalent


@pytest.mark.unit
def test_debt_financing_shifts_npv(
    npv_finance_inputs, fake_filtered_tech_config, fake_cost_dict, subtests
):
    """Adding cheaper debt lowers the WACC and raises NPV vs equity-only."""
    equity_only_inputs = npv_finance_inputs.copy()
    equity_only_inputs["real_discount_rate"] = 0.10

    debt_financed_inputs = equity_only_inputs.copy()
    debt_financed_inputs["debt_rate"] = 0.05
    debt_financed_inputs["debt_equity_ratio"] = 1.0

    prob_equity = _build_npv_problem(equity_only_inputs, fake_filtered_tech_config, fake_cost_dict)
    prob_debt = _build_npv_problem(debt_financed_inputs, fake_filtered_tech_config, fake_cost_dict)

    npv_equity = prob_equity.get_val("npv.NPV_electricity_no1", units="USD")[0]
    npv_debt = prob_debt.get_val("npv.NPV_electricity_no1", units="USD")[0]

    with subtests.test("Lower WACC from debt financing increases NPV"):
        assert npv_debt > npv_equity


@pytest.mark.unit
def test_wacc_config_validators_reject_out_of_range(subtests):
    """debt_rate and debt_equity_ratio must respect their valid ranges."""
    base = {
        "plant_life": 30,
        "real_discount_rate": 0.09,
        "commodity_sell_price_units": "USD/(kW*h)",
    }

    with subtests.test("debt_rate above 1 is rejected"):
        with pytest.raises(ValueError, match="debt_rate"):
            NumpyFinancialNPVFinanceConfig.from_dict({**base, "debt_rate": 1.5})

    with subtests.test("debt_equity_ratio below 0 is rejected"):
        with pytest.raises(ValueError, match="debt_equity_ratio"):
            NumpyFinancialNPVFinanceConfig.from_dict({**base, "debt_equity_ratio": -1.0})
