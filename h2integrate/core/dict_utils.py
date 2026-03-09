import copy
import operator
from functools import reduce

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
