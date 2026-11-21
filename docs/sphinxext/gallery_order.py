"""Configuration for the order of gallery sections and examples. Paths are relative to the
docs/conf.py file.
"""

import itertools
from pathlib import Path

from sphinx.util import logging as sphinx_logging
from sphinx_gallery.sorting import ExplicitOrder


logger = sphinx_logging.getLogger(__name__)

# Gallery sections shall be displayed in the following order.
# Non-matching sections are inserted at the unsorted position

examples_dir_order = [
    # basic demonstration of concepts
    # hybrid generation feeding a downstream product
    "../../examples/01_onshore_steel_mn",
    "../../examples/15_wind_solar_electrolyzer",
    "../../examples/02_texas_ammonia",
    "../../examples/03_methanol",
    "../../examples/12_ammonia_synloop",
    # product chains
    # studies: design optimization, parameter/site sweeps, sizing, several cases in sequence
    "../../examples/05_wind_h2_opt",
    "../../examples/20_solar_electrolyzer_doe",
    "../../examples/22_site_doe",
    "../../examples/27_site_doe_diff",
    # controllers
    "../../examples/13_dispatch_for_electrolyzer",
    "../../examples/14_wind_hydrogen_dispatch",
    "../../examples/18_pyomo_heuristic_dispatch",
    "../../examples/19_simple_dispatch",
    "../../examples/30_pyomo_optimized_dispatch",
    "../../examples/33_peak_load_management_heuristics",
    "../../examples/34_plm_optimized_dispatch",
    "../../examples/35_system_level_control",
    # demand, combiners and splitters, grid buy and sell, feedstocks
    "../../examples/16_natural_gas",
    "../../examples/23_solar_wind_ng_demand",
    "../../examples/24_solar_battery_grid",
    # user-defined models
    "../../examples/06_custom_tech",
    "../../examples/08_wind_electrolyzer",
    # simulation modes
    # post-processing
    # miscellaneous
    "../../examples/04_geo_h2",
    "../../examples/07_run_of_river_plant",
    "../../examples/09_co2",
    "../../examples/10_electrolyzer_om",
    "../../examples/17_splitter_wind_doc_h2",
    "../../examples/21_iron_examples",
    "../../examples/25_sizing_modes",
    "../../examples/26_floris",
    "../../examples/29_wind_ard",
    "../../examples/31_tidal",
    "../../examples/32_multivariable_streams",
    "../../examples/36_nuclear_reactor_htse",
    "../../examples/37_paper_mill",
]

folder_lists = [*examples_dir_order]  # placeholder in case we decide to add other structures


class ExampleSorter(ExplicitOrder):
    """Explicit class ordering that reads the order of examples from a subfolder's
    ``gallery_order.txt``.

    Results should be fed to the sphinx gallery 'within_subsection_order' key.

    The ``gallery_order.txt`` file contains a list of example filenames (without the .py extension)
    in their desired order. Unlisted examples can be placed in bulk with the optional "*". If "*" is
    unused, all examples must be listed, or an error will be raised. Use this if you want to ensure
    that order is intentionally maintained.
    """

    def __init__(self, examples_dir):
        ordered_list = self.read_gallery_order(Path(examples_dir).resolve()) or []
        super().__init__(ordered_list)

    @staticmethod
    def read_gallery_order(examples_dir: Path):
        """Return the list of examples to be sorted according to ``gallery_order.txt``, ignoring
        inline comments.
        """
        if not (gallery_order := examples_dir / "gallery_order.txt").exists():
            return None
        lines = [
            line.strip()
            for line in gallery_order.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

        try:
            unlisted_index = lines.index("*")
        except ValueError:
            unlisted_index = None

        lines = [line + ".py" for line in lines]

        if unlisted_index is None:
            first_half = lines
            last_half = []
        else:
            first_half = lines[:unlisted_index]
            last_half = lines[unlisted_index + 1 :]

        listed_examples = {*first_half, *last_half}
        all_examples = {f.name for f in examples_dir.iterdir() if f.suffix == ".py"}

        nonexistent_examples = listed_examples - all_examples
        missing_examples = all_examples - listed_examples

        relative_path = gallery_order.relative_to(gallery_order.parents[3])
        if nonexistent_examples:
            msg = (
                f"The following examples listed in {relative_path} do not exist: "
                f"{', '.join(nonexistent_examples)}"
            )
            logger.warning(msg)
        if unlisted_index is None and missing_examples:
            msg = (
                f"The following examples are not listed in {relative_path}. Either include them or"
                f" add a '*' to indicate where not listed examples should be placed: "
                f"{', '.join(missing_examples)}"
            )
            logger.warning(msg)

        mid = sorted(missing_examples)
        return first_half + mid + last_half

    def __call__(self, item):
        """Return a string determining the sort order."""
        if not self.ordered_list:
            return item
        return f"{self.ordered_list.index(item):04d}"

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.ordered_list}>"


# Provide the above classes for use in conf.py
section_order = folder_lists
subsection_order = ExampleSorter

_preserve_count = itertools.count()


def preserve_order(item):
    """A sorting key to preserve the original order of items in minigalleries."""
    return next(_preserve_count)
