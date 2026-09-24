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
        return design_dict

    # using lifetime output
    # check that analysis_period is the same as plant life
    if lifetime_opts.get("analysis_period", plant_life) != plant_life:
        old = lifetime_opts["analysis_period"]
        warnings.warn(f"Updating analysis_period from {old} to {plant_life} (plant_life)")

    # check that degradation_varname is the same length as plant life
    if len(lifetime_opts.get(degradation_varname, [0.0] * plant_life)) != plant_life:
        old_len = len(lifetime_opts.get(degradation_varname, [0.0] * plant_life))
        warnings.warn(
            f"Updating '{degradation_varname}' from length {old_len} to length {plant_life}"
        )

    # tile the dc_degration so that its the same length as plant_life
    dc_deg_init = lifetime_opts.get(degradation_varname, [0.0] * plant_life)
    n_repeats = np.ceil(plant_life / len(dc_deg_init))
    degradation = np.tile(dc_deg_init, int(n_repeats))[:plant_life]
    # update analysis_period and degradation_varname in the design dict
    lifetime_opts["analysis_period"] = plant_life
    lifetime_opts[degradation_varname] = degradation.tolist()
    design_dict["Lifetime"].update(lifetime_opts)
    return design_dict
