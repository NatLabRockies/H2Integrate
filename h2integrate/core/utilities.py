import re
import csv
import copy
import operator
from typing import Any
from pathlib import Path
from functools import reduce
from collections import OrderedDict

import yaml
import attrs
import numpy as np
import ruamel.yaml as ry
from attrs import Attribute, field, define

from h2integrate import ROOT_DIR


try:
    from pyxdsm.XDSM import FUNC, XDSM
except ImportError:
    pass


def create_xdsm_from_config(config, output_file="connections_xdsm"):
    """
    Create an XDSM diagram from a given plant configuration and save it to a pdf file.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing technology interconnections.
    output_file : str, optional
        The name of the output file where the XDSM diagram will be saved.
    """
    # Create an XDSM object
    x = XDSM(use_sfmath=True)

    # Use an OrderedDict to keep the order of technologies
    technologies = OrderedDict()
    if "technology_interconnections" not in config:
        return

    for conn in config["technology_interconnections"]:
        technologies[conn[0]] = None  # Source
        technologies[conn[1]] = None  # Destination

    # Add systems to the XDSM
    for tech in technologies.keys():
        tech_label = tech.replace("_", r"\_")
        x.add_system(tech, FUNC, rf"\text{{{tech_label}}}")

    # Add connections
    for conn in config["technology_interconnections"]:
        if len(conn) == 3:
            source, destination, data = conn
        else:
            source, destination, data, label = conn

        if isinstance(data, (list, tuple)) and len(data) >= 2:
            data = f"{data[0]} as {data[1]}"

        if len(conn) == 3:
            connection_label = rf"\text{{{data}}}"
        else:
            connection_label = rf"\text{{{data} {'via'} {label}}}"

        connection_label = connection_label.replace("_", r"\_")

        x.connect(source, destination, connection_label)

    # Write the diagram to a file
    x.write(output_file, quiet=True)
    print(f"XDSM diagram written to {output_file}.pdf")


def merge_shared_inputs(config, input_type):
    """
    Merges two dictionaries from a configuration object and resolves potential conflicts.

    This function combines the dictionaries associated with `shared_parameters` and
    `performance_parameters`, `cost_parameters`, or `finance_parameters` in the provided
    `config` dictionary. If both dictionaries contain the same keys,
    a ValueError is raised to prevent duplicate parameter definitions.

    Parameters:
        config (dict): A dictionary containing configuration data. It must include keys
                       like `shared_parameters` and `{input_type}_parameters`.
        input_type (str): The type of input parameters to merge. Valid values are
                          'performance', 'control', 'cost', or 'finance'.

    Returns:
        dict: A merged dictionary containing parameters from both `shared_parameters`
              and `{input_type}_parameters`. If one of the dictionaries is missing,
              the function returns the existing dictionary.

    Raises:
        ValueError: If duplicate keys are found in `shared_parameters` and
                    `{input_type}_parameters`.
    """

    if f"{input_type}_parameters" in config.keys() and "shared_parameters" in config.keys():
        common_keys = config[f"{input_type}_parameters"].keys() & config["shared_parameters"].keys()
        if common_keys:
            raise ValueError(
                f"Duplicate parameters found: {', '.join(common_keys)}. "
                f"Please define parameters only once in the shared and {input_type} dictionaries."
            )
        return {**config[f"{input_type}_parameters"], **config["shared_parameters"]}
    elif "shared_parameters" not in config.keys():
        return config[f"{input_type}_parameters"]
    else:
        return config["shared_parameters"]


@define(kw_only=True)
class BaseConfig:
    """
    A Mixin class to allow for kwargs overloading when a data class doesn't
    have a specific parameter defined. This allows passing of larger dictionaries
    to a data class without throwing an error.
    """

    @classmethod
    def from_dict(cls, data: dict, strict=True):
        """Maps a data dictionary to an `attr`-defined class.

        TODO: Add an error to ensure that either none or all the parameters are passed in

        Args:
            data : dict
                The data dictionary to be mapped.
            strict: bool
                A flag enabling strict parameter processing, meaning that no extra parameters
                    may be passed in or an AttributeError will be raised.
        Returns:
            cls
                The `attr`-defined class.
        """
        # Check for any inputs that aren't part of the class definition
        if strict is True:
            class_attr_names = [a.name for a in cls.__attrs_attrs__]
            extra_args = [d for d in data if d not in class_attr_names]
            if len(extra_args):
                raise AttributeError(
                    f"The initialization for {cls.__name__} was given extraneous "
                    f"inputs: {extra_args}"
                )

        kwargs = {a.name: data[a.name] for a in cls.__attrs_attrs__ if a.name in data and a.init}

        # Map the inputs must be provided: 1) must be initialized, 2) no default value defined
        required_inputs = [
            a.name for a in cls.__attrs_attrs__ if a.init and a.default is attrs.NOTHING
        ]
        undefined = sorted(set(required_inputs) - set(kwargs))

        if undefined:
            raise AttributeError(
                f"The class definition for {cls.__name__} is missing the following inputs: "
                f"{undefined}"
            )
        return cls(**kwargs)

    def as_dict(self) -> dict:
        """Creates a JSON and YAML friendly dictionary that can be save for future reloading.
        This dictionary will contain only `Python` types that can later be converted to their
        proper `Turbine` formats.

        Returns:
            dict: All key, value pairs required for class re-creation.
        """
        return attrs.asdict(self, filter=attr_filter, value_serializer=attr_serializer)


@define(kw_only=True)
class CostModelBaseConfig(BaseConfig):
    cost_year: int = field(converter=int)


@define(kw_only=True)
class ResizeablePerformanceModelBaseConfig(BaseConfig):
    size_mode: str = field(default="normal")
    flow_used_for_sizing: str | None = field(default=None)
    max_feedstock_ratio: float = field(default=1.0)
    max_commodity_ratio: float = field(default=1.0)

    def __attrs_post_init__(self):
        """Validate sizing parameters after initialization."""
        valid_modes = ["normal", "resize_by_max_feedstock", "resize_by_max_commodity"]
        if self.size_mode not in valid_modes:
            raise ValueError(
                f"Sizing mode '{self.size_mode}' is not a valid sizing mode. "
                f"Options are {valid_modes}."
            )

        if self.size_mode != "normal":
            if self.flow_used_for_sizing is None:
                raise ValueError(
                    "'flow_used_for_sizing' must be set when size_mode is "
                    "'resize_by_max_feedstock' or 'resize_by_max_commodity'"
                )


def attr_serializer(inst: type, field: Attribute, value: Any):
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def attr_filter(inst: Attribute, value: Any) -> bool:
    if inst.init is False:
        return False
    if value is None:
        return False
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return False
    return True


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


def check_plant_config_and_profast_params(
    plant_config_dict: dict, pf_param_dict: dict, plant_config_key: str, pf_config_key: str
):
    """
    Checks for consistency between values in the plant configuration dictionary and the
    ProFAST parameters dictionary.

    This function compares the value associated with `plant_config_key` in `plant_config_dict`
    to the value associated with `pf_config_key` in `pf_param_dict`. If `pf_config_key` is not
    present in `pf_param_dict`, the value from `plant_config_dict` is used as the default.
    If the values are inconsistent, a ValueError is raised with a descriptive message.

    Args:
        plant_config_dict (dict): Dictionary containing plant configuration parameters.
        pf_param_dict (dict): Dictionary containing ProFAST parameter values.
        plant_config_key (str): Key to look up in `plant_config_dict`.
        pf_config_key (str): Key to look up in `pf_param_dict`.

    Raises:
        ValueError: If the values for the specified keys in the two dictionaries are inconsistent.
    """

    if (
        pf_param_dict.get(pf_config_key, plant_config_dict[plant_config_key])
        != plant_config_dict[plant_config_key]
    ):
        msg = (
            f"Inconsistent values provided for {pf_config_key} and {plant_config_key}, "
            f"{pf_config_key} is {pf_param_dict.get(pf_config_key)} but "
            f"{plant_config_key} is {plant_config_dict[plant_config_key]}."
            f"Please check that {pf_config_key} is the same as {plant_config_key} or remove "
            f"{pf_config_key} from pf_params input."
        )
        raise ValueError(msg)


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
                    if isinstance(orig_dict[k], (str, bool, int)):
                        orig_dict[k] = orig_dict.get(k, []) + val[i]
                    elif isinstance(orig_dict[k], (list, np.ndarray)):
                        orig_dict[k] = np.array(val, dtype=float).tolist()
                    else:
                        orig_dict[k] = float(val[i])
            elif isinstance(key, str):
                if isinstance(orig_dict[key], (str, bool, int)):
                    continue
                if orig_dict[key] is None:
                    continue
                if isinstance(orig_dict[key], (list, np.ndarray)):
                    if any(isinstance(v, dict) for v in val):
                        for vii, v in enumerate(val):
                            if isinstance(v, dict):
                                new_val = dict_to_yaml_formatting(v)
                            else:
                                new_val = v if isinstance(v, (str, bool, int)) else float(v)
                            orig_dict[key][vii] = new_val
                    else:
                        new_val = [v if isinstance(v, (str, bool, int)) else float(v) for v in val]
                        orig_dict[key] = new_val
                else:
                    orig_dict[key] = float(val)
    return orig_dict


def get_path(path: str | Path) -> Path:
    """
    Convert a string or Path object to an absolute Path object, prioritizing different locations.

    This function attempts to find the existence of a path in the following order:
    1. As an absolute path.
    2. Relative to the current working directory.
    3. Relative to the H2Integrate package.

    Args:
        path (str | Path): The input path, either as a string or a Path object.

    Raises:
        FileNotFoundError: If the path is not found in any of the locations.

    Returns:
        Path: The absolute path to the file.
    """
    # Store the original path for reference in error messages.
    original_path = path

    # If the input is a string, convert it to a Path object.
    if isinstance(path, str):
        path = Path(path)

    # Check if the path exists as an absolute path.
    if path.exists():
        return path.absolute()

    # If not, try finding the path relative to the current working directory.
    relative_path = Path.cwd() / path
    path = relative_path

    # If the path still doesn't exist, attempt to find it relative to the H2Integrate package.
    if path.exists():
        return path.absolute()

    # Determine the path relative to the H2Integrate package.
    h2i_based_path = ROOT_DIR.parent / Path(original_path)

    path = h2i_based_path

    if path.exists():
        return path.absolute()

    # If the path still doesn't exist in any of the prioritized locations, raise an error.
    raise FileNotFoundError(
        f"File not found in absolute path: {original_path}, relative path: "
        f"{relative_path}, or H2Integrate-based path: "
        f"{h2i_based_path}"
    )


def find_file(filename: str | Path, root_folder: str | Path | None = None):
    """
    This function attempts to find a filepath matching `filename` from a variety of locations
    in the following order:

    1. Relative to the root_folder (if provided)
    2. Relative to the current working directory.
    3. Relative to the H2Integrate package.
    4. As an absolute path if `filename` is already absolute

    Args:
        filename (str | Path): Input filepath
        root_folder (str | Path, optional): Root directory to search for filename in.
            Defaults to None.

    Raises:
        FileNotFoundError: If the path is not found in any of the locations.

    Returns:
        Path: The absolute path to the file.
    """

    # 1. check for file in the root directory
    files = []
    if root_folder is not None:
        root_folder = Path(root_folder)
        # if the file exists in the root directory, return full path
        if Path(root_folder, filename).exists():
            return Path(root_folder, filename).resolve().absolute()

        # check for files within root directory
        files = list(Path(root_folder).glob(f"**/{filename}"))

        if len(files) == 1:
            return files[0].absolute()
        if len(files) > 1:
            raise FileNotFoundError(
                f"Found {len(files)} files in the root directory ({root_folder}) that have "
                f"filename {filename}"
            )

        filename_no_rel = "/".join(
            p
            for p in Path(root_folder, filename).resolve(strict=False).parts
            if p not in Path(root_folder).parts
        )
        files = list(Path(root_folder).glob(f"**/{filename_no_rel}"))
        if len(files) == 1:
            return files[0].absolute()

    # 2. check for file relative to the current working directory
    files_cwd = list(Path.cwd().glob(f"**/{filename}"))
    if len(files_cwd) == 1:
        return files_cwd[0].absolute()

    # 3. check for file relative to the H2Integrate package root
    files_h2i = list(ROOT_DIR.parent.glob(f"**/{filename}"))
    files_h2i = [file for file in files_h2i if "build" not in file.parts]
    if len(files_h2i) == 1:
        return files_h2i[0].absolute()

    # 4. check for as absolute path
    if Path(filename).is_absolute():
        return Path(filename)

    if len(files_cwd) == 0 and len(files_h2i) == 0:
        raise FileNotFoundError(
            f"Did not find any files matching {filename} in the current working directory "
            f"{Path.cwd()} or relative to the H2Integrate package {ROOT_DIR.parent}"
        )
    if root_folder is not None and len(files) == 0:
        raise FileNotFoundError(
            f"Did not find any files matching {filename} in the current working directory "
            f"{Path.cwd()}, relative to the H2Integrate package {ROOT_DIR.parent}, or relative to "
            f"the root directory {root_folder}."
        )
    raise ValueError(
        f"Cannot find unique file: found {len(files_cwd)} files relative to cwd, "
        f"{len(files_h2i)} files relative to H2Integrate root directory, "
        f"{len(files)} files relative to the root folder."
    )


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
                elif isinstance(current_value, (list, tuple)):
                    for i, item in enumerate(current_value):
                        current_value[i] = remove_numpy(item)

    # set fast variables to update values
    loop_dict(fst_vt, [])
    return fst_vt


class Loader(yaml.SafeLoader):
    def __init__(self, stream):
        # root is the parent directory of the parent yaml file
        self._root = get_path(Path(stream.name).parent)

        super().__init__(stream)

    def include(self, node):
        filename = find_file(node.value, self._root)

        with Path.open(filename) as f:
            return yaml.load(f, self.__class__)


Loader.add_constructor("!include", Loader.include)


def load_yaml(filename, loader=Loader) -> dict:
    if isinstance(filename, dict):
        return filename  # filename already yaml dict
    with Path.open(filename) as fid:
        return yaml.load(fid, loader)


def write_yaml(
    instance: dict, foutput: str, convert_np: bool = True, check_formatting: bool = False
) -> None:
    """
    Writes a dictionary to a YAML file using the ruamel.yaml library.

    Args:
        instance (dict): Dictionary to be written to the YAML file.
        foutput (str): Path to the output YAML file.
        convert_np (bool): Whether to convert numpy objects to simple types. Defaults to True.
        check_formatting (bool): Whether to check formatting to convert numpy arrays to lists.
            Defaults to False.

    Returns:
        None
    """

    if convert_np:
        instance = remove_numpy(instance)
    if check_formatting:
        instance = dict_to_yaml_formatting(instance)
    # Write yaml with updated values
    yaml = ry.YAML()
    yaml.default_flow_style = None
    yaml.width = float("inf")
    yaml.indent(mapping=4, sequence=6, offset=3)
    yaml.allow_unicode = False
    with Path(foutput).open("w", encoding="utf-8") as f:
        yaml.dump(instance, f)


def write_readable_yaml(instance: dict, foutput: str | Path):
    """
    Writes a dictionary to a YAML file using the yaml library.

    Args:
        instance (dict): Dictionary to be written to the YAML file.
        foutput (str | Path): Path to the output YAML file.

    Returns:
        None
    """
    instance = dict_to_yaml_formatting(instance)

    with Path(foutput).open("w", encoding="utf-8") as f:
        yaml.dump(instance, f, sort_keys=False, encoding=None, default_flow_style=False)


def make_unique_case_name(folder, proposed_fname, fext):
    """Generate a filename that does not already exist in a user-defined folder.

    Args:
        folder (str | Path): directory that a file is expected to be created in.
        proposed_fname (str): filename (with extension) to check for existence and
            to use as the base file description of a new an unique file name.
        fext (str): file extension, such as ".csv", ".sql", ".yaml", etc.

    Returns:
        str: unique filename that does not yet exist in folder.
    """
    if "." not in fext:
        fext = f".{fext}"

    # if file(s) exist with the same base name, make a new unique filename
    file_base = proposed_fname.split(fext)[0]
    existing_files = [f for f in Path(folder).glob(f"**/*{fext}") if file_base in f.name]
    if len(existing_files) == 0:
        return proposed_fname

    # get past numbers that were used to make unique files by matching
    # filenames against the file base name followed by a number
    past_numbers = [
        int(re.findall(f"{file_base}[0-9]+", str(fname))[0].split(file_base)[-1])
        for fname in existing_files
        if len(re.findall(f"{file_base}[0-9]+", str(fname))) > 0
    ]

    if len(past_numbers) > 0:
        # if multiple files have the same basename followed by a number,
        # take the maximum unique number and add one
        unique_number = int(max(past_numbers) + 1)
        return f"{file_base}{unique_number}{fext}"
    else:
        # if no files have the same basename followed by a number,
        # but do have the same basename, then add a zero to the file basename
        return f"{file_base}0{fext}"


def check_file_format_for_csv_generator(
    csv_fpath, driver_config, check_only=True, overwrite_file=False
):
    """Check csv file format for the csv file used for the CSVGenerator generator.

    Note:
        Future development could include further checking the values within the rows
        of the csv file and more rigorous checking of columns with empty headers.

    Args:
        csv_fpath (str | Path): filepath to csv file used for 'csvgen' generator.
        driver_config (dict): driver configuration dictionary
        check_only (bool, optional): If True, only check if file is error-free and return a boolean.
          If False, also create a valid csv file if errors are found in the original csv file.
          Defaults to True.
        overwrite_file (bool, optional): If True, overwrites the input csv file with possible errors
            removed. If False, writes a new csv file with a unique name. Only used if check_only is
            False. Defaults to False.

    Raises:
        ValueError: If there are errors in the csv file beyond general formatting errors.

    Returns:
        bool | Path: returns a boolean if check_only is True, or a Path object is check_only is
            False. If check_only is True, returns True if the file appears error-free or False
            if errors are found. If check_only is False, returns the filepath of the new csv
            file that should not have errors.
    """
    design_vars = []
    for technology, variables in driver_config["design_variables"].items():
        for key, value in variables.items():
            if value["flag"]:
                design_var = f"{technology}.{key}"
                design_vars.append(design_var)

    name_map = {}

    # below is how OpenMDAO loads in the csv file and searches for invalid variables
    with Path(csv_fpath).open() as f:
        # map header names to absolute names if necessary
        names = re.sub(" ", "", f.readline()).strip().split(",")
        name_map = {name: name for name in names if name in design_vars}

    # make list of invalid design variables (which may be formatting issues)
    invalid_desvars = [name for name in names if name not in name_map]

    if check_only:
        if len(invalid_desvars) == 0:
            return True  # no invalid design variables
        else:
            return False  # found formatting issues/invalid design variables

    if len(invalid_desvars) == 0:  # didn't find errors
        return csv_fpath

    file_txt_to_remove = []
    remove_index = False

    for invalid_var in invalid_desvars:
        if invalid_var != "":
            # check if any invalid variables contain a design variable name
            # this could occur if "invisible" characters are attached to the column name
            contains_dvar = [d for d in design_vars if d in invalid_var]
            if len(contains_dvar) == 1:
                # only one column contains the design variable, but has formatting issue
                txt_to_remove = [
                    rm_txt for rm_txt in invalid_var.split(contains_dvar[0]) if rm_txt != ""
                ]
                file_txt_to_remove.extend(txt_to_remove)

            if len(contains_dvar) > 1:
                # duplicate definitions of the design variable
                msg = (
                    f"{invalid_var} is does not match a unique design variable. The design "
                    f"variables defined in the driver_config file are {design_vars}."
                    f" Please check the csv file {csv_fpath} to only have one column per "
                    "design variable included in the driver config file."
                )
                raise ValueError(msg)

            if len(contains_dvar) == 0:
                # the invalid_desvar column has a variable that isnt a design variable
                msg = (
                    f"{invalid_var} is an invalid design variable. The design "
                    f"variables defined in the driver_config file are {design_vars}."
                    f" Please check the csv file {csv_fpath} to only have the design "
                    "variables included in the driver config file."
                )
                raise ValueError(msg)

        else:
            # theres an empty index column, with a column name of ""
            remove_index = True
            with Path(csv_fpath).open() as f:
                reader = csv.DictReader(f)
                index_col = [i for i, n in enumerate(reader.fieldnames) if n == ""]

    original_file = Path(csv_fpath).open()
    lines = original_file.readlines()
    original_file.close()
    for f_remove in file_txt_to_remove:
        # remove characters that cause formatting issues
        lines = [line.replace(f_remove, "") for line in lines]
    if remove_index:
        # remove the columns that are index columns
        lines = [
            ",".join(lp for li, lp in enumerate(line.split(",")) if li not in index_col)
            for line in lines
        ]

    if not overwrite_file:
        # create a new file name with the same basename as the input csv file
        dirname = Path(csv_fpath).absolute().parent
        fname = Path(csv_fpath).name
        new_fname = make_unique_case_name(dirname, fname, ".csv")
        new_fpath = dirname / new_fname
    else:
        # use the same filepath as the csv file and overwrite it
        new_fpath = Path(csv_fpath).absolute()

    # join the separate lines into one string
    txt = "".join(line for line in lines)
    new_file = Path(new_fpath).open(mode="w+")

    # save the reformatted lines to the file
    new_file.write(txt)
    new_file.close()

    return new_fpath


def print_results(model, includes=None, excludes=None, show_units=True):
    """Print hierarchical inputs plus explicit/implicit outputs (means only) using Rich.

    Order of rows preserves OpenMDAO's original ordering from list_inputs/list_outputs.
    Group rows are emitted lazily the first time a variable within that path appears.
    """

    def _gather_outputs(explicit=True, implicit=False):
        return model.list_outputs(
            explicit=explicit,
            implicit=implicit,
            val=True,
            prom_name=True,
            units=show_units,
            shape=True,
            includes=includes,
            excludes=excludes,
            out_stream=None,
            return_format="list",
        )

    explicit_meta = _gather_outputs(explicit=True, implicit=False)
    implicit_meta = _gather_outputs(explicit=False, implicit=True)

    # Gather inputs (no explicit/implicit split in OpenMDAO API)
    input_meta = model.list_inputs(
        val=True,
        prom_name=True,
        units=show_units,
        shape=True,
        includes=includes,
        excludes=excludes,
        out_stream=None,
        return_format="list",
    )

    def _mean(val):
        if isinstance(val, np.ndarray):
            return "nan" if val.size == 0 else f"{np.mean(val)}"
        if isinstance(val, (int, float, np.number)):
            return f"{val}"
        return "n/a"

    from rich import box
    from rich.table import Table
    from rich.console import Console

    console = Console()

    def _emit_section(title, meta_list, kind_label="outputs"):
        if not meta_list:
            return
        console.print(f"\n{len(meta_list)} {title.lower()} {kind_label}:")
        table = Table(show_header=True, header_style="bold", box=box.MINIMAL, pad_edge=False)
        table.add_column("Variable", overflow="fold")
        table.add_column("Mean", justify="right")
        if show_units:
            table.add_column("Units")
        table.add_column("Shape")
        table.add_column("Promoted name", overflow="fold")

        emitted_groups = set()
        for abs_name, meta in meta_list:
            parts = abs_name.split(".")
            # emit group rows
            for depth in range(len(parts) - 1):
                grp_path = ".".join(parts[: depth + 1])
                if grp_path not in emitted_groups:
                    emitted_groups.add(grp_path)
                    indent = "  " * depth
                    grp_name = parts[depth]
                    if show_units:
                        table.add_row(f"{indent}{grp_name}", "", "", "", "")
                    else:
                        table.add_row(f"{indent}{grp_name}", "", "", "")
            var = parts[-1]
            indent = "  " * (len(parts) - 1)
            mean_raw = _mean(meta.get("val"))
            try:
                val = float(mean_raw)
                units_val_raw = meta.get("units")
                # Format as integer if units are 'year' or variable name is 'cost_year'
                if units_val_raw == "year" or var == "cost_year":
                    mean_val = str(int(val))
                elif abs(val) >= 1e5:
                    formatted = f"{val:,.2f}"
                    mean_val = formatted.rstrip("0")
                    if mean_val.endswith("."):
                        mean_val = mean_val  # Keep e.g. "520." format
                    else:
                        mean_val = mean_val + "." if "." not in mean_val else mean_val
                else:
                    formatted = f"{val:,.4f}"
                    mean_val = formatted.rstrip("0")
                    # Ensure we end with "." if all decimals were zeros
                    if mean_val.endswith("."):
                        pass  # Keep as e.g. "520." or "0."
                    elif "." not in mean_val:
                        mean_val = mean_val + "."
            except (ValueError, TypeError):
                mean_val = str(mean_raw)
            units_val = (
                "n/a"
                if (var == "cost_year" or meta.get("units") is None)
                else str(meta.get("units"))
                if show_units
                else ""
            )
            shape_meta = meta.get("shape", "")
            if var == "cost_year":
                shape_str = "n/a"
            elif isinstance(shape_meta, (tuple, list)) and len(shape_meta) > 0:
                shape_str = str(shape_meta[0])
            else:
                shape_str = "" if shape_meta in (None, "", ()) else str(shape_meta)
            promoted = meta.get("prom_name", "")
            if show_units:
                table.add_row(f"{indent}{var}", mean_val, units_val, shape_str, promoted)
            else:
                table.add_row(f"{indent}{var}", mean_val, shape_str, promoted)
        console.print(table)

    # Emit sections (inside function scope)
    _emit_section("Explicit", input_meta, kind_label="inputs")
    _emit_section("Explicit", explicit_meta, kind_label="outputs")
    _emit_section("Implicit", implicit_meta, kind_label="outputs")

    # structured return
    def _structured(meta_list):
        return {
            name: {
                "mean": _mean(meta.get("val")),
                **(
                    {
                        "units": (
                            "n/a"
                            if name.split(".")[-1] == "cost_year" or meta.get("units") is None
                            else meta.get("units")
                        )
                    }
                    if show_units
                    else {}
                ),
                "shape": (
                    "n/a"
                    if name.split(".")[-1] == "cost_year"
                    else meta.get("shape")[0]
                    if isinstance(meta.get("shape"), (tuple, list)) and len(meta.get("shape")) > 0
                    else ""
                    if meta.get("shape") in (None, "", ())
                    else meta.get("shape")
                ),
                "promoted_name": meta.get("prom_name"),
            }
            for name, meta in meta_list
        }

    return {
        "inputs": _structured(input_meta),
        "explicit_outputs": _structured(explicit_meta),
        "implicit_outputs": _structured(implicit_meta),
    }
