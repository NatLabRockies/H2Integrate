import networkx as nx


# BELOW HERE IS THE INFORMATION YOU HAVE
tech_connections = [
    ["boat", "desalination", "raw_water"],
    ["desalination", "electrolyzer", "water"],
    ["wind", "elec_combiner", "electricity"],
    ["solar", "elec_combiner", "electricity"],
    ["elec_combiner", "battery", "electricity"],
    ["battery", "elec_combiner_2", "electricity"],
    ["elec_combiner", "elec_combiner_2", "electricity"],
    ["elec_combiner_2", "electrolyzer", "electricity"],
    ["electrolyzer", "h2_storage", "hydrogen"],
    ["electrolyzer", "h2_combiner", "hydrogen"],
    ["h2_storage", "h2_combiner", "hydrogen"],
    ["h2_combiner", "haber_bosch", "hydrogen"],
    ["grid", "haber_bosch", "electricity"],
    ["haber_bosch", "nh3_demand", "ammonia"],
]

input_techs = [
    "boat",
    "desalination",
    "wind",
    "solar",
    "battery",
    "electrolyzer",
    "h2_storage",
    "haber_bosch",
    "grid",
]
demand_tech = "nh3_demand"

technology_graph = nx.DiGraph()
for connection in tech_connections:
    technology_graph.add_edge(connection[0], connection[1], commodity=connection[2])

# techs and their output commodities
techs_to_commodities = {
    ("wind", "electricity"),
    ("solar", "electricity"),
    ("battery", "electricity"),
    ("electrolyzer", "hydrogen"),
    ("h2_storage", "hydrogen"),
    ("boat", "raw_water"),
    ("desalination", "water"),
    ("grid", "electricity"),
    ("haber_bosch", "ammonia"),
}

upstreams = {
    # (input_commodity, technology): {upstream techs that make input_commodity}
    ("electricity", "haber_bosch"): {"grid"},
    ("hydrogen", "haber_bosch"): {"electrolyzer", "h2_storage"},
    ("electricity", "electrolyzer"): {"solar", "battery", "wind"},
    ("water", "electrolyzer"): {"desalination", "water_storage"},
    ("raw_water", "desalination"): {"boat"},
}

hb_e2a = 1.75
hb_h2a = 2.0
pem_e2h = 0.5
pem_w2h = 5.0
des_rw2w = 1 / 5
conversion_factors = {
    # (input_commodity, converter tech point, output_commodity): conversion factor
    ("electricity", "haber_bosch", "ammonia"): hb_e2a,
    ("hydrogen", "haber_bosch", "ammonia"): hb_h2a,
    ("electricity", "electrolyzer", "hydrogen"): pem_e2h,
    ("water", "electrolyzer", "hydrogen"): pem_w2h,
    ("raw_water", "desalination", "water"): des_rw2w,
}

ammonia_demand = 80.0
converter_technologies = {k[1] for k, v in upstreams.items()}
# ABOVE HERE IS THE INFORMATION YOU HAVE


# how to convert the ammonia demand to the demand of other components at each step
# ex: grid_electricity_demand = ammonia_demand*1.75
# grid demand is ammonia_demand*1.75
# how do we get the
# 0) electricity demand for grid
# 1) hydrogen demand for the electrolyzer and h2 storage system
# 2) electricity demand for the wind, solar, and battery system
# 3) water demand for the desalination plant
# 4) raw_water demand for the boat

# --- put attempted solution here ---

# --- put attempted solution above ---


# Below can be used to test your result to see if its been done properly
nh3_dmd = 80.0
# NOTE: the expected results formatting is a little stupid
expected_results = {
    ("electricity", "haber_bosch"): nh3_dmd * hb_e2a,  # electricity demand for grid
    ("hydrogen", "haber_bosch"): nh3_dmd
    * hb_h2a,  # hydrogen demand for the electrolyzer and h2 storage system
    ("electricity", "electrolyzer"): nh3_dmd
    * hb_h2a
    * pem_e2h,  # electricity demand for the wind, solar, and battery system
    ("water", "electrolyzer"): nh3_dmd
    * hb_h2a
    * pem_w2h,  # water demand for the desalination plant
    ("raw_water", "desalination"): nh3_dmd
    * hb_h2a
    * pem_w2h
    * des_rw2w,  # raw_water demand for the boat
}
