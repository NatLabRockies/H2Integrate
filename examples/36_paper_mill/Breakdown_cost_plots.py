# """
# Created on Fri May 15 07:38:06 2026

# @author: mkoleva
# """

# import pandas as pd
# import matplotlib.pyplot as plt

# # Load Excel file
# file_path = "Breakdown_costs_per_scenario.xlsx"
# df = pd.read_excel(file_path, sheet_name="Sheet1", header=None)

# # Scenario labels — edit however you prefer
# scenarios = [
#     "Paper + Pulp",
#     "SAF with H2",
#     "SAF with low-carbon H2",
#     "Paper + Pulp\nSAF with H2",
#     "Paper + Pulp\nSAF with low-carbon H2"
# ]

# # Extract cost component names
# components = df.iloc[3:, 0].values

# # Build scenario value arrays (sum of appropriate columns)
# records = {}
# records["Paper + Pulp"] = df.iloc[3:, [1, 2, 3]].astype(float).sum(axis=1).values
# records["SAF with H2"] = df.iloc[3:, [3]].astype(float).sum(axis=1).values
# records["SAF with low-carbon H2"] = df.iloc[3:, [4]].astype(float).sum(axis=1).values
# records["Paper + Pulp\nSAF with H2"] = df.iloc[3:, [5, 6, 7]].astype(float).sum(axis=1).values
# results = df.iloc[3:, [8, 9, 10]]
# records["Paper + Pulp\nSAF with low-carbon H2"] = results.astype(float).sum(axis=1).values

# # Build DataFrame
# plot_df = pd.DataFrame(records, index=components)
# plot_df = plot_df[scenarios]  # order consistently

# # Assign custom colors
# colors = []
# for comp in plot_df.index:
#     if "CapEx" in comp:
#         colors.append("navy")
#     elif "OpEx" in comp:
#         colors.append("orange")
#     elif "Feedstock" in comp:
#         colors.append("deepskyblue")
#     elif "Taxes" in comp:
#         colors.append("lightpink")
#     elif "Finances" in comp:
#         colors.append("yellowgreen")
#     else:
#         colors.append(None)   # Let matplotlib choose default

# # Plotting
# plt.figure(figsize=(10, 6))
# bottom = [0] * len(scenarios)

# for idx, comp in enumerate(plot_df.index):
#     plt.bar(
#         scenarios,
#         plot_df.loc[comp],
#         bottom=bottom,
#         color=colors[idx],
#         label=comp
#     )
#     bottom = [bottom[i] + plot_df.loc[comp][i] for i in range(len(scenarios))]

# plt.xlabel("Scenario")
# plt.ylabel("Cost ($/kg)")
# plt.title("Cost Breakdown per Scenario")

# # FORCE horizontal x-axis labels
# plt.xticks(rotation=0, ha="center")

# plt.legend()
# plt.tight_layout()

# plt.savefig("stacked_cost_breakdown_final.png", dpi=300)
# plt.show()

import textwrap

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# -------------------------------------------------------------
# LOAD EXCEL
# -------------------------------------------------------------
file_path = "Breakdown_costs_per_scenario.xlsx"
df = pd.read_excel(file_path, sheet_name="Sheet1", header=None)

# -------------------------------------------------------------
# READ STRUCTURE
# -------------------------------------------------------------
scenario_row = df.iloc[0, 1:].tolist()
product_row = df.iloc[1, 1:].tolist()
components = df.iloc[2:, 0].astype(str).str.strip().tolist()
values = df.iloc[2:, 1:].astype(float)

# -------------------------------------------------------------
# CLEAN NANS
# -------------------------------------------------------------
valid = [i for i, s in enumerate(scenario_row) if str(s) != "nan"]
scenario_row = [scenario_row[i] for i in valid]
product_row = [product_row[i] for i in valid]
values = values.iloc[:, valid]

# -------------------------------------------------------------
# MULTILINE SCENARIO LABELS (automatic wrapping)
# -------------------------------------------------------------
scenario_row_wrapped = ["\n".join(textwrap.wrap(s, width=18)) for s in scenario_row]

# -------------------------------------------------------------
# BUILD MULTIINDEX
# -------------------------------------------------------------
tuples = list(zip(scenario_row_wrapped, product_row))
df_plot = pd.DataFrame(values.values, index=components, columns=pd.MultiIndex.from_tuples(tuples))

# -------------------------------------------------------------
# FLATTENED PRODUCT LABELS
# -------------------------------------------------------------
flat_products = product_row

# -------------------------------------------------------------
# GROUP POSITIONS FOR SCENARIO LABELS
# -------------------------------------------------------------
scenario_groups = {}
for idx, scen in enumerate(scenario_row_wrapped):
    scenario_groups.setdefault(scen, []).append(idx)

x = np.arange(len(flat_products))

# -------------------------------------------------------------
# COLOR MAP
# -------------------------------------------------------------
color_map = {
    "CapEx ($/kg)": "navy",
    "OpEx ($/kg)": "orange",
    "Feedstock ($/kg)": "deepskyblue",
    "Taxes ($/kg)": "lightpink",
    "Finances ($/kg)": "yellowgreen",
}

# -------------------------------------------------------------
# PLOT
# -------------------------------------------------------------
plt.figure(figsize=(18, 7))

bottom = np.zeros(len(x))

for comp in components:
    y = df_plot.loc[comp].values
    plt.bar(x, y, bottom=bottom, color=color_map[comp], label=comp)
    bottom += y

# -------------------------------------------------------------
# X-AXIS LABELS (PRODUCT LEVEL)
# -------------------------------------------------------------
plt.xticks(x, flat_products, rotation=0, ha="center")

# -------------------------------------------------------------
# Y-AXIS LABEL
# -------------------------------------------------------------
plt.ylabel("Levelized cost ($/kg)")

plt.title("Cost Breakdown by Product and Scenario")

# -------------------------------------------------------------
# SCENARIO LABELS (CENTERED ABOVE GROUPS)
# -------------------------------------------------------------
ymin, ymax = plt.ylim()
for scen, idxs in scenario_groups.items():
    center = np.mean(idxs)
    plt.text(
        center, ymax + ymax * 0.04, scen, ha="center", va="bottom", fontsize=11, fontweight="bold"
    )

plt.ylim(ymin, ymax * 1.25)

plt.legend(title="Cost Component", bbox_to_anchor=(1.02, 1), loc="upper left")
plt.tight_layout()
plt.show()
