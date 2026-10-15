import warnings

import numpy as np


def check_pysam_input_params(user_dict, pysam_options):
    """Checks for different values provided in two dictionaries that have the general format::

        value = input_dict[group][group_param]

    Args:
        user_dict (dict): top-level performance model inputs formatted to align with
            the corresponding PySAM module.
        pysam_options (dict): additional PySAM module options.

    Raises:
        ValueError: if there are two different values provided for the same key.

    """
    for group, group_params in user_dict.items():
        if group in pysam_options:
            for key in group_params.keys():
                if key in pysam_options:
                    if pysam_options[group][key] != user_dict[group][key]:
                        msg = (
                            f"Inconsistent values provided for parameter {key} in {group} Group."
                            f"pysam_options has value of {pysam_options[group][key]} "
                            f"but user also specified value of {user_dict[group][key]}. "
                        )
                        raise ValueError(msg)
    return


def apply_non_native_lifetime_degradation(generation, degradation, plant_life):
    """Apply annual degradation percentages to a single-year generation profile.

    The input generation profile is repeated once per plant year and scaled by that
    year's degradation factor. A single degradation value is treated as a constant
    annual rate, increasing linearly from zero degradation in the first year. If
    multiple values are supplied, each is the total degradation percentage for its
    corresponding year.

    Args:
        generation (np.ndarray): Single-year generation time series.
        degradation (list): Annual degradation percentage(s), not fractions.
            A single value specifies the annual rate; multiple values specify the
            degradation percentage for each year.
        plant_life (int): Number of years in the plant lifetime.

    Returns:
        np.ndarray: Concatenated lifetime generation profile after applying
        degradation.
    """
    # degradation = self.design_dict["Lifetime"]["ac_degradation"]
    if not isinstance(generation, np.ndarray):
        generation = np.array(generation)

    # A single rate represents linear annual degradation across the plant life.
    if len(degradation) == 1:
        year_indices = np.arange(plant_life)
        degradation_factors = 1 - degradation[0] * year_indices / 100
        degradation_factors[0] = 1.0
    else:
        # Multiple rates provide the degradation percentage for each year.
        degradation_factors = 1 - np.asarray(degradation) / 100
    # Scale one generation profile per year, then join them into a lifetime series.
    generation = np.concatenate(
        [generation * degradation_factor for degradation_factor in degradation_factors]
    )
    return generation


def check_pysam_lifetime_options(design_dict, plant_life, degradation_varname):
    """If using lifetime output from a PySAM model, ensure that analysis_period
    and the annual degradation are both the same length as the plant life.

    Args:
        design_dict (dict): dictionary of PySAM module options.
        plant_life (int): lifetime of the plant
        degradation_varname (str): name of the degradation variable for the PySAM
        model using this function

    Returns:
        dict: dictionary with `Lifetime` options updated to reflect the plant life
    """
    lifetime_opts = design_dict.get("Lifetime", {})
    if not bool(lifetime_opts.get("system_use_lifetime_output", 0)):
        # not using lifetime output
        return design_dict

    # using lifetime output

    # check that analysis_period is the same as plant life
    if lifetime_opts.get("analysis_period", plant_life) != plant_life:
        old = lifetime_opts["analysis_period"]
        warnings.warn(
            f"Updating analysis_period from {old} to {plant_life} (plant_life)",
            UserWarning,
            stacklevel=3,
        )

    # check that degradation_varname is the same length as plant life
    degradation = lifetime_opts.get(degradation_varname)
    if degradation is None:
        degradation = [0.0] * plant_life
    else:
        degradation = list(degradation)
        if not degradation:
            raise ValueError(f"Lifetime.{degradation_varname} must contain at least one value.")

    if len(degradation) != plant_life:
        msg = (
            f"Updating '{degradation_varname}' from length "
            f"{len(degradation)} to length {plant_life}"
        )
        warnings.warn(
            msg,
            UserWarning,
            stacklevel=2,
        )
        # Repeat or truncate the supplied annual values to match the plant life.
        degradation = np.resize(degradation, plant_life).tolist()

    # update analysis_period and degradation_varname in the design dict
    lifetime_opts["analysis_period"] = plant_life
    lifetime_opts[degradation_varname] = degradation
    design_dict["Lifetime"].update(lifetime_opts)
    return design_dict
