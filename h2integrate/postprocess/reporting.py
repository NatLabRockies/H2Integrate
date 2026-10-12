"""Reporting and diagram-generation utilities for completed H2Integrate models."""

from collections import OrderedDict

import numpy as np
from rich import box
from rich.table import Table
from rich.console import Console


try:
    from pyxdsm.XDSM import FUNC, XDSM
except ImportError:
    XDSM = None
    FUNC = None


def print_results(model, includes=None, excludes=None, show_units=True):
    """Print hierarchical OpenMDAO inputs and outputs using Rich.

    This utility is intended for a model that has completed OpenMDAO setup. It
    queries the model's listed variables, prints a compact hierarchical report,
    and returns the same information in a structured dictionary for callers that
    need to consume the results programmatically.

    Args:
        model (openmdao.core.System): Set-up OpenMDAO model whose inputs and
            outputs are reported.
        includes (str | list[str] | None): OpenMDAO variable patterns to include.
        excludes (str | list[str] | None): OpenMDAO variable patterns to exclude.
        show_units (bool): Whether to include units in printed and returned
            metadata.

    Returns:
        dict: Mapping with ``inputs``, ``explicit_outputs``, and
            ``implicit_outputs`` entries. Each entry maps an absolute variable
            name to its mean value, shape, promoted name, and, when requested,
            units.
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

    def _mean(value):
        if isinstance(value, np.ndarray):
            return "nan" if value.size == 0 else f"{np.mean(value)}"
        if isinstance(value, int | float | np.number):
            return f"{value}"
        return "n/a"

    console = Console()

    def _emit_section(title, metadata, kind_label="outputs"):
        if not metadata:
            return
        console.print(f"\n{len(metadata)} {title.lower()} {kind_label}:")
        table = Table(show_header=True, header_style="bold", box=box.MINIMAL, pad_edge=False)
        table.add_column("Variable", overflow="fold")
        table.add_column("Mean", justify="right")
        if show_units:
            table.add_column("Units")
        table.add_column("Shape")
        table.add_column("Promoted name", overflow="fold")

        emitted_groups = set()
        for absolute_name, metadata_item in metadata:
            parts = absolute_name.split(".")
            for depth in range(len(parts) - 1):
                group_path = ".".join(parts[: depth + 1])
                if group_path not in emitted_groups:
                    emitted_groups.add(group_path)
                    indent = "  " * depth
                    group_name = parts[depth]
                    if show_units:
                        table.add_row(f"{indent}{group_name}", "", "", "", "")
                    else:
                        table.add_row(f"{indent}{group_name}", "", "", "")
            variable = parts[-1]
            indent = "  " * (len(parts) - 1)
            mean_raw = _mean(metadata_item.get("val"))
            try:
                value = float(mean_raw)
                units = metadata_item.get("units")
                if units == "year" or variable == "cost_year":
                    mean_value = str(int(value))
                elif abs(value) >= 1e5:
                    mean_value = f"{value:,.2f}".rstrip("0")
                    if not mean_value.endswith(".") and "." not in mean_value:
                        mean_value += "."
                else:
                    mean_value = f"{value:,.4f}".rstrip("0")
                    if not mean_value.endswith(".") and "." not in mean_value:
                        mean_value += "."
            except (ValueError, TypeError):
                mean_value = str(mean_raw)
            units_value = (
                "n/a"
                if variable == "cost_year" or metadata_item.get("units") is None
                else str(metadata_item.get("units"))
                if show_units
                else ""
            )
            shape = metadata_item.get("shape", "")
            if variable == "cost_year":
                shape_value = "n/a"
            elif isinstance(shape, tuple | list) and shape:
                shape_value = str(shape[0])
            else:
                shape_value = "" if shape in (None, "", ()) else str(shape)
            promoted_name = metadata_item.get("prom_name", "")
            if show_units:
                table.add_row(
                    f"{indent}{variable}",
                    mean_value,
                    units_value,
                    shape_value,
                    promoted_name,
                )
            else:
                table.add_row(f"{indent}{variable}", mean_value, shape_value, promoted_name)
        console.print(table)

    _emit_section("Explicit", input_meta, kind_label="inputs")
    _emit_section("Explicit", explicit_meta)
    _emit_section("Implicit", implicit_meta)

    def _structured(metadata):
        return {
            name: {
                "mean": _mean(metadata_item.get("val")),
                **(
                    {
                        "units": (
                            "n/a"
                            if name.split(".")[-1] == "cost_year"
                            or metadata_item.get("units") is None
                            else metadata_item.get("units")
                        )
                    }
                    if show_units
                    else {}
                ),
                "shape": (
                    "n/a"
                    if name.split(".")[-1] == "cost_year"
                    else metadata_item.get("shape")[0]
                    if isinstance(metadata_item.get("shape"), tuple | list)
                    and metadata_item.get("shape")
                    else ""
                    if metadata_item.get("shape") in (None, "", ())
                    else metadata_item.get("shape")
                ),
                "promoted_name": metadata_item.get("prom_name"),
            }
            for name, metadata_item in metadata
        }

    return {
        "inputs": _structured(input_meta),
        "explicit_outputs": _structured(explicit_meta),
        "implicit_outputs": _structured(implicit_meta),
    }


def create_xdsm(plant_config, outfile="connections_xdsm"):
    """Create an XDSM diagram from a plant configuration.

    Args:
        plant_config (dict): Plant configuration containing technology
            interconnections.
        outfile (str): Base filename for the generated XDSM output.

    Returns:
        None: The diagram is written to ``outfile`` by pyXDSM.

    Raises:
        ValueError: If no technology interconnections are configured.
        ImportError: If pyXDSM is not installed.
    """
    if not plant_config.get("technology_interconnections", []):
        raise ValueError(
            "Generating an XDSM diagram requires technology interconnections, "
            "but none were found."
        )
    if XDSM is None:
        raise ImportError("pyXDSM is required to generate an XDSM diagram.")

    x = XDSM(use_sfmath=True)
    technologies = OrderedDict()
    for connection in plant_config["technology_interconnections"]:
        technologies[connection[0]] = None
        technologies[connection[1]] = None

    for tech in technologies:
        tech_label = tech.replace("_", r"\_")
        x.add_system(tech, FUNC, rf"\text{{{tech_label}}}")

    for connection in plant_config["technology_interconnections"]:
        if len(connection) == 3:
            source, destination, data = connection
        else:
            source, destination, data, label = connection

        if isinstance(data, list | tuple) and len(data) >= 2:
            data = f"{data[0]} as {data[1]}"
        connection_label = (
            rf"\text{{{data}}}" if len(connection) == 3 else rf"\text{{{data} {'via'} {label}}}"
        )
        x.connect(source, destination, connection_label.replace("_", r"\_"))

    x.write(outfile, quiet=True)
    print(f"XDSM diagram written to {outfile}.pdf")
