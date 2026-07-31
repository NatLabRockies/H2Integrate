import os

from h2integrate import EXAMPLE_DIR
from h2integrate.core.h2integrate_model import H2IntegrateModel


os.chdir(EXAMPLE_DIR / "36_paper_mill")

model = H2IntegrateModel("36_paper_mill_mn.yaml")


model.setup()
model.run()
model.post_process()


import ast

import numpy as np
import pandas as pd


def flatten_value_to_series(value, length):
    """Convert scalar, list, array, or string-literal into a fixed-length vector."""
    if isinstance(value, dict):
        return [None] * length

    if isinstance(value, np.ndarray):
        value = value.flatten().tolist()

    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                value = parsed
            else:
                value = [parsed]
        except (ValueError, SyntaxError):
            value = [value]

    if isinstance(value, list):
        series = value
    else:
        series = [value]

    if len(series) < length:
        series = series + [""] * (length - len(series))

    return series[:length]


def export_outputs_masha_excel(model, excel_file="paper_mill_outputs_masha.xlsx"):
    """
    Produces an Excel file with:
    Sheet 1: Main outputs in Masha's desired format (variables as columns, values down rows)
    Sheet 2: Dictionary-type outputs expanded into columns
    """

    outputs = model.prob.model.list_outputs(val=True, units=True, out_stream=None)

    nondict_values = {}
    dict_values = {}
    max_len = 1

    for name, meta in outputs:
        val = meta["val"]

        # Convert literal dictionary strings
        if isinstance(val, str):
            try:
                parsed = ast.literal_eval(val)
                if isinstance(parsed, dict):
                    val = parsed
            except (ValueError, SyntaxError):
                pass

        if isinstance(val, dict):
            dict_values[name] = val
            continue

        nondict_values[name] = val

        if isinstance(val, np.ndarray):
            max_len = max(max_len, val.size)
        elif isinstance(val, list):
            max_len = max(max_len, len(val))
        elif isinstance(val, str):
            try:
                parsed = ast.literal_eval(val)
                if isinstance(parsed, list):
                    max_len = max(max_len, len(parsed))
            except (ValueError, SyntaxError):
                pass

    # Sheet 1 — main outputs
    sheet1 = pd.DataFrame({"index": list(range(1, max_len + 1))})
    for name, val in nondict_values.items():
        sheet1[name] = flatten_value_to_series(val, max_len)

    # Sheet 2 — dictionary outputs
    dict_rows = []
    for name, dct in dict_values.items():
        flat = {f"{name}.{k}".replace(" ", "_"): v for k, v in dct.items()}
        dict_rows.append(flat)

    sheet2 = pd.DataFrame(dict_rows)

    # Write Excel using openpyxl (always available)
    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        sheet1.to_excel(writer, sheet_name="MainOutputs_Masha", index=False)
        sheet2.to_excel(writer, sheet_name="CostBreakdowns", index=False)

    print(f"Excel file successfully written: {excel_file}")


export_outputs_masha_excel(model, "paper_mill_outputs_masha.xlsx")
