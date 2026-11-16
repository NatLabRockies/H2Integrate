"""Example of an iron mine sending processed ore pellets to a separate DRI iron plant and EAF

In this example, iron ore pellets are produced at different iron mine locations in NE Minnesota.
These mines send processed ore pellets to a separate iron DRI plant located outside Chicago.
The example is run with two iron mine models: the simple mine model (`single_site_iron.yaml`) and
the NRRI mine model (`single_site_iron_nrri.yaml`), which also models the natural gas and diesel
consumed at the mine.

For each mine model, four different cases are generated for four different iron mine setups in
`test_inputs.csv` (simple mine model) or `test_inputs_nrri.csv` (NRRI mine model).
The first two cases generate standard blast furnace grade pellets at two different mine locations.
The second two cases generate DR grade pellets at the same location, with the output capacity
varied to show how the capacity of the mine does not affect the levelized cost of iron_ore pellets
(LCOI), nor does it affect the final cost of the sponge_iron produced by DRI (LCOS) or the cost
of the steel produced by the EAF (LCOS).

"""

from pathlib import Path

import pandas as pd

from h2integrate import H2IntegrateModel
from h2integrate.tools.run_cases import modify_tech_config, load_tech_config_cases


casenames = [
    "Standard Iron - Hibbing",
    "Standard Iron - Northshore",
    "DR Grade Iron - Northshore",
    "DR Grade Iron - Northshore (adjusted)",
]

columns = pd.MultiIndex.from_tuples(
    [
        ("Levelized Cost", "[USD/kg]"),
        ("Capex", "[USD]"),
        ("Fixed Opex", "[USD/year]"),
        ("Variable Opex", "[USD/year]"),
    ]
)


def get_costs(model: H2IntegrateModel, product: str) -> list[float]:
    """Return the levelized cost, CapEx, fixed OpEx, and variable OpEx of one product."""
    subgroup = f"finance_subgroup_{product}"
    return [
        float(model.model.get_val(f"{subgroup}.price_{product}", units="USD/kg")[0]),
        float(model.model.get_val(f"{subgroup}.total_capex_adjusted", units="USD")[0]),
        float(model.model.get_val(f"{subgroup}.total_opex_adjusted", units="USD/year")[0]),
        float(model.model.get_val(f"{subgroup}.total_varopex_adjusted", units="USD/year")[0]),
    ]


def run_mine_cases(config_file: str, case_file: str) -> dict[str, pd.DataFrame]:
    """Run each mine case and tabulate the costs of the iron ore, sponge iron, and steel."""
    model = H2IntegrateModel(config_file)
    model.run()
    model.post_process()

    cases = load_tech_config_cases(Path(case_file))
    costs = {"iron_ore": [], "sponge_iron": [], "steel": []}
    for casename in casenames:
        model = modify_tech_config(model, cases[casename])
        model.run()
        for product, product_costs in costs.items():
            product_costs.append(get_costs(model, product))

    return {
        product: pd.DataFrame(product_costs, index=casenames, columns=columns)
        for product, product_costs in costs.items()
    }


mine_models = {
    "Simple iron mine model": ("single_site_iron.yaml", "test_inputs.csv"),
    "NRRI iron mine model": ("single_site_iron_nrri.yaml", "test_inputs_nrri.csv"),
}

# Compare the Capex, Fixed Opex, and Variable Opex across the 4 cases for each mine model
for mine_model, (config_file, case_file) in mine_models.items():
    tables = run_mine_cases(config_file, case_file)
    print(f"\n{mine_model}\n")
    print(tables["iron_ore"])
    print()
    print(tables["sponge_iron"])
    print()
    # Steel results are only reported for the DR grade pellet cases
    print(tables["steel"].iloc[2:])
