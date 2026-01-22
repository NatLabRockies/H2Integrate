import numpy as np

from h2integrate.converters.hydrogen.pem_model.PEM_H2_LT_electrolyzer_Clusters import (
    PEM_H2_Clusters as PEMClusters,
)


def create_1MW_reference_PEM(curve_coeff=None):
    """Create a 1MW reference PEM electrolyzer cluster.

    Args:
        curve_coeff: Optional curve coefficients for the electrolyzer efficiency curve.
            Defaults to None.

    Returns:
        PEMClusters: A configured PEM electrolyzer cluster object with 1MW capacity
            and 30-year plant life.
    """
    pem_param_dict = {
        "eol_eff_percent_loss": 10,
        "uptime_hours_until_eol": 77600,
        "include_degradation_penalty": True,
        "turndown_ratio": 0.1,
        "curve_coeff": curve_coeff,
    }
    pem = PEMClusters(cluster_size_mw=1, plant_life=30, **pem_param_dict)
    return pem


def get_electrolyzer_BOL_efficiency():
    """Get the beginning-of-life (BOL) efficiency of a reference electrolyzer.

    Creates a 1MW reference PEM electrolyzer and extracts its BOL efficiency
    at the highest operating point.

    Returns:
        float: BOL efficiency in kWh/kg, rounded to 2 decimal places.
    """
    pem_1MW = create_1MW_reference_PEM()
    bol_eff = pem_1MW.output_dict["BOL Efficiency Curve Info"]["Efficiency [kWh/kg]"].values[-1]

    return np.round(bol_eff, 2)


def size_electrolyzer_for_hydrogen_demand(
    hydrogen_production_capacity_required_kgphr,
    size_for="BOL",
    electrolyzer_degradation_power_increase=None,
):
    """Size an electrolyzer based on hydrogen production demand.

    Calculates the required electrolyzer capacity in MW to meet a specified
    hydrogen production rate, accounting for either beginning-of-life (BOL)
    or end-of-life (EOL) efficiency.

    Args:
        hydrogen_production_capacity_required_kgphr: Required hydrogen production
            capacity in kg per hour.
        size_for: Sizing criterion, either "BOL" for beginning-of-life or "EOL"
            for end-of-life efficiency. Defaults to "BOL".
        electrolyzer_degradation_power_increase: Fractional increase in power
            consumption due to degradation (e.g., 0.1 for 10% increase).
            Required if size_for="EOL". Defaults to None.

    Returns:
        float: Required electrolyzer capacity in MW.
    """
    electrolyzer_energy_kWh_per_kg_estimate_BOL = get_electrolyzer_BOL_efficiency()
    if size_for == "BOL":
        electrolyzer_capacity_MW = (
            hydrogen_production_capacity_required_kgphr
            * electrolyzer_energy_kWh_per_kg_estimate_BOL
            / 1000
        )
    elif size_for == "EOL":
        electrolyzer_energy_kWh_per_kg_estimate_EOL = (
            electrolyzer_energy_kWh_per_kg_estimate_BOL
            * (1 + electrolyzer_degradation_power_increase)
        )
        electrolyzer_capacity_MW = (
            hydrogen_production_capacity_required_kgphr
            * electrolyzer_energy_kWh_per_kg_estimate_EOL
            / 1000
        )

    return electrolyzer_capacity_MW.item()
