from pathlib import Path

__version__ = "0.8.0"

ROOT_DIR = Path(__file__).resolve().parent
EXAMPLE_DIR = ROOT_DIR.parent / "examples"
RESOURCE_DEFAULT_DIR = ROOT_DIR.parent / "resource_files"
H2I_LIBRARY_DIR = ROOT_DIR.parent / "library"

# isort: off
from h2integrate.core.h2integrate_model import H2IntegrateModel
from h2integrate.core.file_utils import load_yaml, write_readable_yaml, write_yaml
from h2integrate.core.inputs.validation import load_driver_yaml, load_plant_yaml, load_tech_yaml
