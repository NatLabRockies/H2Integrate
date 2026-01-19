"""
Code adapted from NREL's WISDEM tool.
"""

from pathlib import Path

import numpy as np
import jsonschema as json

from h2integrate.core.utilities import load_yaml, write_yaml


fschema_tech = Path(__file__).parent / "tech_schema.yaml"
fschema_plant = Path(__file__).parent / "plant_schema.yaml"
fschema_driver = Path(__file__).parent / "driver_schema.yaml"


# ---------------------
# This is for when the defaults are in another file
def nested_get(indict, keylist):
    rv = indict
    for k in keylist:
        rv = rv[k]
    return rv


def nested_set(indict, keylist, val):
    rv = indict
    for i, k in enumerate(keylist):
        rv = rv[k] if i != len(keylist) - 1 else val


def integrate_defaults(instance: dict, defaults: dict, yaml_schema: dict) -> dict:
    """
    Integrates default values from a dictionary into another dictionary.

    Args:
        instance (dict): Dictionary to be updated with default values.
        defaults (dict): Dictionary containing default values.
        yaml_schema (dict): Dictionary containing the schema of the YAML file.

    Returns:
        dict: Updated dictionary with default values integrated.
    """
    # Prep iterative validator
    # json.validate(self.wt_init, yaml_schema)
    validator = json.Draft7Validator(yaml_schema)
    errors = validator.iter_errors(instance)

    # Loop over errors
    for e in errors:
        # If the error is due to a missing required value, try to set it to the default
        if e.validator == "required":
            for k in e.validator_value:
                if k not in e.instance.keys():
                    mypath = e.absolute_path.copy()
                    mypath.append(k)
                    v = nested_get(defaults, mypath)
                    if isinstance(v, dict) or isinstance(v, list) or v in ["name", "material"]:
                        # Too complicated to just copy over default, so give it back to the user
                        raise (e)
                    print("WARNING: Missing value,", list(mypath), ", so setting to:", v)
                    nested_set(instance, mypath, v)
        raise (e)
    return instance


def simple_types(indict: dict) -> dict:
    """
    Recursively converts numpy array elements within a nested dictionary to lists and ensures
    all values are simple types (float, int, dict, bool, str).

    Args:
        indict (dict): The dictionary to process.

    Returns:
        dict: The processed dictionary with numpy arrays converted to lists and
            unsupported types to empty strings.
    """

    def convert(value):
        if isinstance(value, np.ndarray):
            return convert(value.tolist())
        elif isinstance(value, dict):
            return {key: convert(value) for key, value in value.items()}
        elif isinstance(value, (list, tuple, set)):
            return [convert(item) for item in value]  # treat all as list
        elif isinstance(value, (np.generic)):
            return value.item()  # convert numpy primitives to python primitive underlying
        elif isinstance(value, (float, int, bool, str)):
            return value  # this should be the end case
        else:
            return ""

    return convert(indict)


# ---------------------
# See: https://python-jsonschema.readthedocs.io/en/stable/faq/#why-doesn-t-my-schema-s-default-property-set-the-default-on-my-instance
def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for prop, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(prop, subschema["default"])

        yield from validate_properties(validator, properties, instance, schema)

    return json.validators.extend(validator_class, {"properties": set_defaults})


DefaultValidatingDraft7Validator = extend_with_default(json.Draft7Validator)


def _validate(finput, fschema, defaults=True):
    """
    Validates a dictionary against a schema and returns the validated dictionary.

    Args:
        finput (dict or str): Dictionary or path to the YAML file to be validated.
        fschema (dict or str): Dictionary or path to the schema file to validate against.
        defaults (bool): Flag to indicate if default values should be integrated.

    Returns:
        dict: Validated dictionary.
    """
    schema_dict = fschema if isinstance(fschema, dict) else load_yaml(fschema)
    input_dict = finput if isinstance(finput, dict) else load_yaml(finput)
    validator = DefaultValidatingDraft7Validator if defaults else json.Draft7Validator
    validator(schema_dict).validate(input_dict)
    return input_dict


# ---------------------
def load_tech_yaml(finput):
    return _validate(finput, fschema_tech)


def load_plant_yaml(finput):
    plant_config = _validate(finput, fschema_plant)

    if int(plant_config["plant"]["simulation"]["n_timesteps"]) != 8760:
        msg = (
            "H2Integrate does not currently support simulations that are less than or "
            "greater than 1-year. Please ensure that "
            "plant_config['plant']['simulation']['n_timesteps'] is set to 8760."
        )
        raise ValueError(msg)
    if int(plant_config["plant"]["simulation"]["dt"]) != 3600:
        msg = (
            "H2Integrate does not currently support simulations with a time step that is "
            "less than or greater than 1-hour. Please ensure that "
            "plant_config['plant']['simulation']['dt'] is set to 3600."
        )
        raise ValueError(msg)
    return plant_config


def load_driver_yaml(finput):
    return _validate(finput, fschema_driver)


def tech_yaml(instance: dict, foutput: str) -> None:
    _validate(instance, fschema_tech, defaults=False)
    # Ensure the file output has a .yaml suffix
    if not foutput.endswith(".yaml"):
        foutput += ".yaml"
    write_yaml(instance, foutput)
    return foutput
