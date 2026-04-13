import copy
import operator
from functools import reduce
from collections import Counter

import numpy as np


def dict_to_yaml_formatting(orig_dict):
    """Recursive method to convert arrays to lists and numerical entries to floats.
    This is primarily used before writing a dictionary to a YAML file to ensure
    proper output formatting.

    Args:
        orig_dict (dict): input dictionary

    Returns:
        dict: input dictionary with reformatted values.
    """
    for key, val in orig_dict.items():
        if isinstance(val, dict):
            tmp = dict_to_yaml_formatting(orig_dict.get(key, {}))
            orig_dict[key] = tmp
        else:
            if isinstance(key, list):
                for i, k in enumerate(key):
                    if isinstance(orig_dict[k], str | bool | int):
                        orig_dict[k] = orig_dict.get(k, []) + val[i]
                    elif isinstance(orig_dict[k], list | np.ndarray):
                        orig_dict[k] = np.array(val, dtype=float).tolist()
                    else:
                        orig_dict[k] = float(val[i])
            elif isinstance(key, str):
                if isinstance(orig_dict[key], str | bool | int):
                    continue
                if orig_dict[key] is None:
                    continue
                if isinstance(orig_dict[key], list | np.ndarray):
                    if any(isinstance(v, dict) for v in val):
                        for vii, v in enumerate(val):
                            if isinstance(v, dict):
                                new_val = dict_to_yaml_formatting(v)
                            else:
                                new_val = v if isinstance(v, str | bool | int) else float(v)
                            orig_dict[key][vii] = new_val
                    else:
                        new_val = [v if isinstance(v, str | bool | int) else float(v) for v in val]
                        orig_dict[key] = new_val
                else:
                    orig_dict[key] = float(val)
    return orig_dict


def remove_numpy(fst_vt: dict) -> dict:
    """
    Recursively converts numpy array elements within a nested dictionary to lists and ensures
    all values are simple types (float, int, dict, bool, str) for writing to a YAML file.

    Args:
        fst_vt (dict): The dictionary to process.

    Returns:
        dict: The processed dictionary with numpy arrays converted to lists
            and unsupported types to simple types.
    """

    def get_dict(vartree, branch):
        return reduce(operator.getitem, branch, vartree)

    # Define conversion dictionary for numpy types
    conversions = {
        np.int_: int,
        np.intc: int,
        np.intp: int,
        np.int8: int,
        np.int16: int,
        np.int32: int,
        np.int64: int,
        np.uint8: int,
        np.uint16: int,
        np.uint32: int,
        np.uint64: int,
        np.single: float,
        np.double: float,
        np.longdouble: float,
        np.csingle: float,
        np.cdouble: float,
        np.float16: float,
        np.float32: float,
        np.float64: float,
        np.complex64: float,
        np.complex128: float,
        np.bool_: bool,
        np.ndarray: lambda x: x.tolist(),
    }

    def loop_dict(vartree, branch):
        if not isinstance(vartree, dict):
            return fst_vt
        for var in vartree.keys():
            branch_i = copy.copy(branch)
            branch_i.append(var)
            if isinstance(vartree[var], dict):
                loop_dict(vartree[var], branch_i)
            else:
                current_value = get_dict(fst_vt, branch_i[:-1])[branch_i[-1]]
                data_type = type(current_value)
                if data_type in conversions:
                    get_dict(fst_vt, branch_i[:-1])[branch_i[-1]] = conversions[data_type](
                        current_value
                    )
                elif isinstance(current_value, list | tuple):
                    for i, item in enumerate(current_value):
                        current_value[i] = remove_numpy(item)

    # set fast variables to update values
    loop_dict(fst_vt, [])
    return fst_vt


def update_defaults(orig_dict, keyname, new_val):
    """Recursive method to update all entries in a dictionary with key 'keyname'
    with value 'new_val'

    Args:
        orig_dict (dict): dictionary to update
        keyname (str): key corresponding to value to update
        new_val (any): value to use for ``keyname``

    Returns:
        dict: updated version of orig_dict
    """
    for key, val in orig_dict.items():
        if isinstance(val, dict):
            tmp = update_defaults(orig_dict.get(key, {}), keyname, new_val)
            orig_dict[key] = tmp
        else:
            if isinstance(key, list):
                for i, k in enumerate(key):
                    if k == keyname:
                        orig_dict[k] = new_val
                    else:
                        orig_dict[k] = orig_dict.get(key, []) + val[i]
            elif isinstance(key, str):
                if key == keyname:
                    orig_dict[key] = new_val
    return orig_dict


def update_keyname(orig_dict, init_key, new_keyname):
    """Recursive method to copy value of ``orig_dict[init_key]`` to ``orig_dict[new_keyname]``

    Args:
        orig_dict (dict): dictionary to update.
        init_key (str): existing key
        new_keyname (str): new key to replace ``init_key``

    Returns:
        dict: updated dictionary
    """

    for key, val in orig_dict.copy().items():
        if isinstance(val, dict):
            tmp = update_keyname(orig_dict.get(key, {}), init_key, new_keyname)
            orig_dict[key] = tmp
        else:
            if isinstance(key, list):
                for i, k in enumerate(key):
                    if k == init_key:
                        orig_dict.update({new_keyname: orig_dict.get(k)})
                    else:
                        orig_dict[k] = orig_dict.get(key, []) + val[i]
            elif isinstance(key, str):
                if key == init_key:
                    orig_dict.update({new_keyname: orig_dict.get(key)})
    return orig_dict


def remove_keynames(orig_dict, init_key):
    """Recursive method to remove keys from a dictionary.

    Args:
        orig_dict (dict): input dictionary
        init_key (str): key name to remove from dictionary

    Returns:
        dict: dictionary without any keys named `init_key`
    """

    for key, val in orig_dict.copy().items():
        if isinstance(val, dict):
            tmp = remove_keynames(orig_dict.get(key, {}), init_key)
            orig_dict[key] = tmp
        else:
            if isinstance(key, list):
                for i, k in enumerate(key):
                    if k == init_key:
                        orig_dict.pop(k)
                    else:
                        orig_dict[k] = orig_dict.get(key, []) + val[i]
            elif isinstance(key, str):
                if key == init_key:
                    orig_dict.pop(key)
    return orig_dict


def rename_dict_keys(input_dict, init_keyname, new_keyname):
    """Rename ``input_dict[init_keyname]`` to ``input_dict[new_keyname]``

    Args:
        input_dict (dict): dictionary to update
        init_keyname (str): existing key to replace
        new_keyname (str): new keyname

    Returns:
        dict: updated dictionary
    """
    input_dict = update_keyname(input_dict, init_keyname, new_keyname)
    input_dict = remove_keynames(input_dict, init_keyname)
    return input_dict


def check_inputs(prob, tech: str, tech_info: dict, tech_config_path: str):
    """Check the user-input technology configuration inputs against the
    instantiated technology configuration classes to ensure that:

    1. All user-input parameters are used in at least 1 configuration class
    2. User-input `shared_parameters` are shared across at least 2 configuration classes
    3. User-input parameters that are not shared are only used in 1 configuration class

    Args:
        prob (om.Problem): OpenMDAO problem defined in H2IntegrateModel
        tech (str): name of technology that the tech_info is for.
        tech_info (dict): technology input dictionary, including the
            technology model names and `model_inputs`.
        tech_config_path (str or Path, optional): path to the technology
            configuration file. Used in error messages to help the user
            locate the problematic section.

    Raises:
        AttributeError: Raised if any of the 3 conditions are not met.
    """
    # Only check models that have a control strategy or dispatch rule set
    if not {"control_strategy", "dispatch_rule_set"}.intersection(tech_info):
        return

    # Only check for shared inputs when the system contains at least one technology
    # in addition to a performance and control model
    check_keys = ("control_strategy", "dispatch_rule_set", "cost_model", "performance_model")
    minimal_keys = {"control_strategy", "performance_model"}
    overlap = set(tech_info).intersection(check_keys)
    if not overlap.difference(minimal_keys):
        return

    msg = None
    control_sys = None
    dispatch_sys = None
    cost_sys = None
    perf_sys = None
    group = getattr(prob.model.plant, tech)

    # Rebuild the model inputs dictionary from the initialized technology parameters
    control_params = {}
    dispatch_params = {}
    cost_params = {}
    performance_params = {}
    if "control_strategy" in tech_info:
        if (control_sys := getattr(group, tech_info["control_strategy"]["model"])) is not None:
            control_params = control_sys.config.as_dict()
    if "dispatch_rule_set" in tech_info:
        if (dispatch_sys := getattr(group, tech_info["dispatch_rule_set"]["model"])) is not None:
            dispatch_params = dispatch_sys.config.as_dict()
    if "cost_model" in tech_info:
        if (cost_sys := getattr(group, tech_info["cost_model"]["model"])) is not None:
            cost_params = cost_sys.config.as_dict()
    if "performance_model" in tech_info:
        if (perf_sys := getattr(group, tech_info["performance_model"]["model"])) is not None:
            performance_params = perf_sys.config.as_dict()
    if "cost_model" in tech_info and "performance_model" in tech_info:
        # Handle case with combined cost and performance model
        if tech_info["cost_model"]["model"] == tech_info["performance_model"]["model"]:
            cost_sys = None
            cost_params = {}

    # Check for overlapping keys between any two sets of configurations to reconstruct
    # the shared parameters, and create a restructured configuration
    all_parameters = (control_params, dispatch_params, cost_params, performance_params)
    _share_check = Counter([x for el in all_parameters for x in set(el)])
    shared = {k for k, v in _share_check.items() if v > 1}
    shared_params = {k: control_params.pop(k) for k in shared.intersection(control_params)}
    shared_params |= {k: dispatch_params.pop(k) for k in shared.intersection(dispatch_params)}
    shared_params |= {k: cost_params.pop(k) for k in shared.intersection(cost_params)}
    shared_params |= {k: performance_params.pop(k) for k in shared.intersection(performance_params)}
    restructured_params = {
        "control_parameters": control_params,
        "dispatch_parameters": dispatch_params,
        "cost_parameters": cost_params,
        "performance_parameters": performance_params,
        "shared_parameters": shared_params,
    }

    tech_location = f"the '{tech}' section of {tech_config_path}"

    # Flag any extra parameterizations provided by the user that should have either been
    # shared but were not or were inappropriately shared
    for param_key, vals in restructured_params.items():
        # check that the parameter key exists in both the user-provided model_inputs and
        # the restructured parameters
        if (user_params := tech_info["model_inputs"].get(param_key)) is None:
            continue

        # Only throw errors when the user provided extraneous parameterizations
        user_extras = set(user_params).difference(vals)
        if not user_extras:
            continue

        if param_key == "shared_parameters":
            unnecessary_shared = [
                (user_extras.intersection(other_params), other_key)
                for other_key, other_params in restructured_params.items()
            ]
            unnecessary_shared = [el for el in unnecessary_shared if el[0]]  # remove the empty sets
            if unnecessary_shared:
                if len(unnecessary_shared) == 1:
                    unshared_params, other_key = unnecessary_shared[0]
                    msg = (
                        f"The parameter(s): {unnecessary_shared} found in shared_parameters"
                        f" but should be in {other_key} for {tech_location}"
                    )
                else:
                    mapping = "\n\t".join(
                        f"{level} should contain: {keys}" for keys, level in unnecessary_shared
                    )
                    msg = (
                        f"The following parameter sets were found in shared_parameters but should"
                        f" be in the following sections for {tech_location}:"
                        f"\n\t{mapping}"
                    )
            else:
                msg = (
                    f"The parameter(s): {user_extras} found in shared_parameters"
                    f" are not used by any of the models for {tech_location}"
                )
            raise AttributeError(msg)

        shared_overlap = user_extras.intersection(restructured_params.get("shared_parameters", {}))
        if shared_overlap:
            msg = (
                f"The parameter(s) {shared_overlap} found in {param_key}"
                f" should be under shared_parameters for {tech_location}"
            )
        msg = (
            f"The parameter(s) {user_extras} found in {param_key} are not used for "
            f"{tech_location}"
        )
        raise AttributeError(msg)
