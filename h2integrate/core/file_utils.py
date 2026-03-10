import re
import csv
import copy
from pathlib import Path

import yaml
import ruamel.yaml as ry
from yaml.nodes import ScalarNode
from yaml.composer import Composer
from yaml.resolver import BaseResolver

from h2integrate import ROOT_DIR
from h2integrate.core.dict_utils import remove_numpy, dict_to_yaml_formatting


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
            return Path(root_folder, filename).absolute()

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


class DuplicateKeyError(Exception):
    """Exception raised when a duplicate YAML key is found.

    Args:
        message (:obj:str): The duplicate key error message to be displayed.
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class Loader(yaml.SafeLoader):
    def __init__(self, stream):
        # root is the parent directory of the parent yaml file
        self._root = get_path(Path(stream.name).parent)

        super().__init__(stream)

    def include(self, node):
        filename = find_file(node.value, self._root)

        return load_yaml(filename)

    def compose_node(self, parent, index):
        """Custom implementation to include line numbers that account for all lines, including
        blank spaces that align with user anticipated 1-indexing.
        """
        line = self.line
        node = Composer.compose_node(self, parent, index)
        node.__line__ = line + 1
        return node

    def construct_mapping(self, node, deep=False):
        """Hooks into the ``yaml.SafeLoader.construct_mapping`` routine to create line number
        mappings for all keys and values, which enables duplicate key error handling.

        Two copies of node are created to avoid errors when run through the validation schema as
        the ``__line__{key}`` and ``__line__`` keys in the key and value nodes are not represented
        by the schema, and therefore raise an error during validation.
        """
        numbered_node = copy.deepcopy(node)
        numbered_nodes = []
        for key_node, _ in numbered_node.value:
            shadow_key_node = ScalarNode(
                tag=BaseResolver.DEFAULT_SCALAR_TAG, value="__line__" + key_node.value
            )
            shadow_value_node = ScalarNode(
                tag=BaseResolver.DEFAULT_SCALAR_TAG, value=key_node.__line__
            )
            numbered_nodes.append((shadow_key_node, shadow_value_node))

        numbered_node.value += numbered_nodes
        mapping = self.check_duplicate_keys(numbered_node, node, deep)
        return mapping

    def check_duplicate_keys(self, numbered_node, node, deep=False):
        """Raises an error for duplicate keys and calls the ``SafeLoader.construct_mapping()``
        routine to create the final dictionary mappings.
        """
        unique_keys = set()
        for key_node, _ in numbered_node.value:
            if ":merge" in key_node.tag:
                continue
            key = self.construct_object(key_node, deep=deep)
            if key in unique_keys:
                raise DuplicateKeyError(f"Duplicate '{key}' key found at line {key_node.__line__}.")
            unique_keys.add(key)

        mapping = super().construct_mapping(node, deep)
        return mapping


Loader.add_constructor("!include", Loader.include)


def load_yaml(filename, loader=Loader) -> dict:
    if isinstance(filename, dict):
        return filename  # filename already yaml dict
    with Path.open(filename) as fid:
        try:
            return yaml.load(fid, loader)
        except DuplicateKeyError as e:
            raise ValueError(f"Duplicate key found in {filename}: {e.message}") from e


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
