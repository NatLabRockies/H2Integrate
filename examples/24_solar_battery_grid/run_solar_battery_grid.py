import copy

from h2integrate import H2IntegrateModel
from h2integrate.core.file_utils import load_yaml


top_level_config = load_yaml("solar_battery_grid.yaml")
base_driver_config = load_yaml(top_level_config["driver_config"])
base_tech_config = load_yaml(top_level_config["technology_config"])
base_plant_config = load_yaml(top_level_config["plant_config"])

variants = {
    "half_year": {
        "dt": 900,  # 15 minutes
        "n_timesteps": 17520,
    },
    "annual": {
        "dt": 3600,  # 1 hour
        "n_timesteps": 8760,
    },
    "two_year": {
        "dt": 10800,  # 3 hours
        "n_timesteps": 5840,
    },
}


def _fmt(value, digits=2):
    return f"{float(value):,.{digits}f}"


results = []

for variant_name, variant in variants.items():
    driver_config = copy.deepcopy(base_driver_config)
    plant_config = copy.deepcopy(base_plant_config)
    tech_config = copy.deepcopy(base_tech_config)

    driver_config.setdefault("general", {})["create_om_reports"] = False
    plant_config["plant"]["simulation"]["dt"] = variant["dt"]
    plant_config["plant"]["simulation"]["n_timesteps"] = variant["n_timesteps"]

    h2i = H2IntegrateModel(
        {
            "name": f"{top_level_config['name']}_{variant_name}",
            "system_summary": top_level_config["system_summary"],
            "driver_config": driver_config,
            "technology_config": tech_config,
            "plant_config": plant_config,
        }
    )

    print(f"Running variant: {variant_name}")
    h2i.run()

    total_load_served = h2i.prob.get_val(
        "electrical_load_demand.total_electricity_produced", units="kW*h"
    )[0]
    total_solar = h2i.prob.get_val("solar.total_electricity_produced", units="kW*h")[0]
    total_grid_buy = h2i.prob.get_val("grid_buy.total_electricity_produced", units="kW*h")[0]
    battery_cf = h2i.prob.get_val("battery.standard_capacity_factor", units="percent")[0]
    solar_cf = h2i.prob.get_val("solar.capacity_factor", units="percent")[0]
    lcoe = h2i.prob.get_val("finance_subgroup_renewables.LCOE")[0]
    percent_load_missed = h2i.prob.get_val("electrical_load_demand.percent_load_missed")[0]
    curtailment_percent = h2i.prob.get_val("electrical_load_demand.curtailment_percent")[0]

    results.append(
        {
            "variant": variant_name,
            "years": variant["n_timesteps"] * variant["dt"] / 31_536_000,
            "dt_hours": variant["dt"] / 3600,
            "n_timesteps": variant["n_timesteps"],
            "lcoe": lcoe,
            "load_served_mwh": total_load_served / 1000,
            "solar_mwh": total_solar / 1000,
            "grid_buy_mwh": total_grid_buy / 1000,
            "solar_cf_pct": solar_cf,
            "battery_cf_pct": battery_cf,
            "load_missed_pct": percent_load_missed,
            "curtailment_pct": curtailment_percent,
        }
    )


header = (
    "variant",
    "sim years",
    "dt (h)",
    "n_steps",
    "LCOE ($/kWh)",
    "load served (MWh)",
    "solar gen (MWh)",
    "grid buy (MWh)",
    "solar CF (%)",
    "battery std CF (%)",
    "load missed (%)",
    "curtailment (%)",
)
rows = [header]
rows.extend(
    (
        result["variant"],
        _fmt(result["years"], 2),
        _fmt(result["dt_hours"], 2),
        str(result["n_timesteps"]),
        _fmt(result["lcoe"], 4),
        _fmt(result["load_served_mwh"], 2),
        _fmt(result["solar_mwh"], 2),
        _fmt(result["grid_buy_mwh"], 2),
        _fmt(result["solar_cf_pct"], 2),
        _fmt(result["battery_cf_pct"], 2),
        _fmt(result["load_missed_pct"], 2),
        _fmt(result["curtailment_pct"], 2),
    )
    for result in results
)

col_widths = [max(len(row[i]) for row in rows) for i in range(len(header))]


def _print_row(row):
    print("  ".join(value.ljust(col_widths[i]) for i, value in enumerate(row)))


print("\nSummary of example 24 variants")
_print_row(header)
_print_row(tuple("-" * width for width in col_widths))
for row in rows[1:]:
    _print_row(row)
