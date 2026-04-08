"""
Generate an interactive class hierarchy visualization for H2Integrate.

This script scans the h2integrate package to discover all classes and their
inheritance relationships, then produces an interactive HTML visualization
(zoomable/scrollable) suitable for embedding in the Jupyter Book docs.

Visual encoding:
  - **Shape**  → model category (converter, storage, transporter, etc.)
  - **Color**  → product / application group (electricity, chemical, metal, etc.)
  - **Border width** → inheritance depth (thicker = higher-level parent)

Usage:
    python docs/generate_class_hierarchy.py

Outputs:
    docs/_static/class_hierarchy.html  — interactive graph
"""

import os
import re
import ast
import math
from pathlib import Path

import networkx as nx
from pyvis.network import Network

from h2integrate import ROOT_DIR


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = ROOT_DIR.parent
OUTPUT_HTML = REPO_ROOT / "docs" / "_static" / "class_hierarchy.html"

# Directories / path fragments that indicate test code (case-insensitive check)
TEST_INDICATORS = {"test", "tests", "conftest", "test_"}

# We only show H2I-native classes; external bases (OpenMDAO, attrs, etc.)
# are excluded from the visualization entirely.
EXTERNAL_BASES_TO_KEEP: set[str] = set()

# ---------------------------------------------------------------------------
# Category detection rules: (directory substring -> (model_category, product))
# Order matters -- first match wins.
#   model_category  → controls node SHAPE
#   product         → controls node COLOR (via color group mapping below)
# ---------------------------------------------------------------------------
CATEGORY_RULES = [
    ("core", ("Core", "General")),
    # --- Electricity-producing converters ---
    ("converters/wind", ("Converter", "Wind")),
    ("converters/solar", ("Converter", "Solar")),
    ("converters/nuclear", ("Converter", "Nuclear")),
    ("converters/grid", ("Converter", "Grid")),
    ("converters/water_power", ("Converter", "Water Power")),
    ("converters/natural_gas", ("Converter", "Natural Gas")),
    ("converters/hopp", ("Converter", "HOPP")),
    # --- Chemical converters ---
    ("converters/hydrogen", ("Converter", "Hydrogen")),
    ("converters/ammonia", ("Converter", "Ammonia")),
    ("converters/methanol", ("Converter", "Methanol")),
    ("converters/co2", ("Converter", "CO2")),
    ("converters/nitrogen", ("Converter", "Nitrogen")),
    ("converters/water", ("Converter", "Water")),
    # --- Metal converters ---
    ("converters/iron", ("Converter", "Iron")),
    ("converters/steel", ("Converter", "Steel")),
    # --- Catch-all converter ---
    ("converters", ("Converter", "Other")),
    # --- Non-converter categories ---
    ("storage", ("Storage", "General")),
    ("resource", ("Resource", "General")),
    ("finances", ("Finance", "General")),
    ("transporters", ("Transporter", "General")),
    ("control", ("Control", "General")),
    ("simulation", ("Simulation", "General")),
    ("tools", ("Tools", "General")),
    ("postprocess", ("Post-processing", "General")),
    ("preprocess", ("Pre-processing", "General")),
]

# ---------------------------------------------------------------------------
# Shape by model category
# ---------------------------------------------------------------------------
CATEGORY_SHAPES_PYVIS = {
    "Core": "ellipse",
    "Converter": "dot",
    "Storage": "diamond",
    "Resource": "triangle",
    "Finance": "star",
    "Transporter": "square",
    "Control": "hexagon",
    "Simulation": "triangleDown",
    "Tools": "box",
    "Post-processing": "box",
    "Pre-processing": "box",
}

# ---------------------------------------------------------------------------
# Color by broad application group
# Products are mapped to a broad group, each group gets one color.
# ---------------------------------------------------------------------------
PRODUCT_TO_GROUP = {
    "General": "Core / General",
    "Wind": "Renewables",
    "Solar": "Renewables",
    "Water Power": "Renewables",
    "HOPP": "Renewables",
    "Nuclear": "Other Elec. Generators",
    "Grid": "Other Elec. Generators",
    "Natural Gas": "Other Elec. Generators",
    "Hydrogen": "Hydrogen",
    "Ammonia": "Chemical",
    "Methanol": "Chemical",
    "CO2": "Chemical",
    "Nitrogen": "Chemical",
    "Water": "Chemical",
    "Iron": "Metal",
    "Steel": "Metal",
    "Other": "Other",
}

GROUP_COLORS = {
    "Core / General": "#555555",
    "Renewables": "#4A90D9",
    "Other Elec. Generators": "#1B3A5C",
    "Hydrogen": "#2E7D32",
    "Chemical": "#66BB6A",
    "Metal": "#D84315",
    "Control": "#00ACC1",
    "Other": "#F5C542",
}

# Patterns used to detect control-related classes by name.
# If a class name matches any of these, its color group is overridden to "Control".
CONTROL_NAME_PATTERNS = re.compile(r"control|pyomo|openloop|open_loop", re.IGNORECASE)

# Border width range for inheritance depth
MAX_BORDER_WIDTH = 5
MIN_BORDER_WIDTH = 1


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _is_test_path(filepath: Path) -> bool:
    """Return True if the file path looks like it belongs to test code."""
    parts = filepath.parts
    for part in parts:
        lower = part.lower()
        if lower in TEST_INDICATORS or lower.startswith("test_"):
            return True
    if filepath.stem.lower().startswith("test_") or filepath.stem.lower() == "conftest":
        return True
    return False


def _rel_mod_path(filepath: Path) -> str:
    """Return the filepath relative to the repo root using forward slashes."""
    try:
        return str(filepath.relative_to(ROOT_DIR)).replace("\\", "/")
    except ValueError:
        return str(filepath).replace("\\", "/")


def _classify(filepath: Path) -> tuple[str, str]:
    """Determine the (model_category, product) for a class based on its file path."""
    rel = _rel_mod_path(filepath)
    for pattern, cat_tuple in CATEGORY_RULES:
        if pattern in rel:
            return cat_tuple
    return ("Other", "Other")


def _resolve_base_name(base_node: ast.expr) -> str | None:
    """Extract a human-readable base-class name from an AST node."""
    if isinstance(base_node, ast.Name):
        return base_node.id
    if isinstance(base_node, ast.Attribute):
        # e.g. om.ExplicitComponent -> ExplicitComponent
        return base_node.attr
    if isinstance(base_node, ast.Subscript):
        # e.g. Generic[T] -> Generic
        return _resolve_base_name(base_node.value)
    return None


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def scan_classes(package_root: Path):
    """Walk the package tree and return class info.

    Returns
    -------
    classes : dict
        {class_name: {"bases": [str], "file": Path, "category": str}}
        If multiple classes share a name, the module path is prepended to
        disambiguate.
    """
    raw: list[dict] = []

    for dirpath, _dirnames, filenames in os.walk(package_root):
        dirpath = Path(dirpath)
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            filepath = dirpath / fname
            if _is_test_path(filepath):
                continue
            try:
                source = filepath.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(filepath))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = []
                for b in node.bases:
                    bname = _resolve_base_name(b)
                    if bname:
                        bases.append(bname)
                category, subcategory = _classify(filepath)
                raw.append(
                    {
                        "name": node.name,
                        "bases": bases,
                        "file": filepath,
                        "model_category": category,
                        "product": subcategory,
                    }
                )

    # Detect name collisions and disambiguate
    from collections import Counter

    name_counts = Counter(r["name"] for r in raw)
    classes: dict[str, dict] = {}
    for r in raw:
        name = r["name"]
        if name_counts[name] > 1:
            # Prefix with the relative module path to disambiguate
            module = _rel_mod_path(r["file"]).replace("/", ".").removesuffix(".py")
            key = f"{module}.{name}"
        else:
            key = name
        classes[key] = {
            "bases": r["bases"],
            "file": r["file"],
            "model_category": r["model_category"],
            "product": r["product"],
        }

    return classes


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

# Classes to exclude from the visualization entirely.
# We filter out all config/dataclass definitions — only performance, cost,
# and other "model" classes are shown.
CONFIG_PATTERN = re.compile(r"Config$", re.IGNORECASE)
EXCLUDE_CLASSES = {
    "BaseConfig",
}


def build_graph(classes: dict) -> nx.DiGraph:
    """Build a directed graph of class inheritance (edges point from parent to child)."""
    G = nx.DiGraph()

    # Build a set of all known H2I class names for quick lookup
    known_names = set(classes.keys())
    # Also build short-name -> full-key mapping (for resolving base names)
    short_to_full: dict[str, list[str]] = {}
    for key in classes:
        short = key.rsplit(".", 1)[-1] if "." in key else key
        short_to_full.setdefault(short, []).append(key)

    def resolve(base_name: str) -> str | None:
        """Resolve a base class name to a node key, or None to skip."""
        if base_name in known_names:
            return base_name
        candidates = short_to_full.get(base_name, [])
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            # Ambiguous — pick the one from core if available
            for c in candidates:
                if "core" in c.lower():
                    return c
            return candidates[0]
        # External base — keep only the interesting ones
        if base_name in EXTERNAL_BASES_TO_KEEP:
            return base_name
        return None

    def _is_excluded(name: str) -> bool:
        """Return True if the class should be excluded (configs, etc.)."""
        if name in EXCLUDE_CLASSES:
            return True
        if CONFIG_PATTERN.search(name):
            return True
        return False

    # Add all H2I class nodes (skip configs)
    for key, info in classes.items():
        short_name = key.rsplit(".", 1)[-1] if "." in key else key
        if _is_excluded(short_name):
            continue
        model_cat = info.get("model_category", "Other")
        product = info.get("product", "General")
        G.add_node(
            key,
            label=short_name,
            model_category=model_cat,
            product=product,
            title=f"{short_name}\n{_rel_mod_path(info['file'])}\n[{model_cat} / {product}]",
        )

    # Add edges (parent -> child) — only between H2I classes already in the graph
    for key, info in classes.items():
        short_name = key.rsplit(".", 1)[-1] if "." in key else key
        if _is_excluded(short_name):
            continue
        if key not in G:
            continue
        for base_name in info["bases"]:
            parent = resolve(base_name)
            if parent is None:
                continue
            # Only add edges to parents that are already in the graph (H2I classes).
            # Do NOT add external nodes.
            if parent not in G:
                continue
            G.add_edge(parent, key)

    return G


# ---------------------------------------------------------------------------
# Inheritance depth computation
# ---------------------------------------------------------------------------


def _compute_depths(G: nx.DiGraph) -> dict[str, int]:
    """Compute inheritance depth for each node (0 = root, increases for children)."""
    depths: dict[str, int] = {}
    roots = [n for n in G if G.in_degree(n) == 0]
    for root in roots:
        queue = [(root, 0)]
        visited = {root}
        while queue:
            node, d = queue.pop(0)
            depths[node] = max(depths.get(node, 0), d)
            for child in G.successors(node):
                if child not in visited:
                    visited.add(child)
                    queue.append((child, d + 1))
    for n in G.nodes:
        if n not in depths:
            depths[n] = 0
    return depths


def _border_width(depth: int, max_depth: int) -> float:
    """Compute border width: thicker for roots, thinner for deeply inherited."""
    if max_depth == 0:
        return MAX_BORDER_WIDTH
    return max(
        MIN_BORDER_WIDTH,
        MAX_BORDER_WIDTH - depth * (MAX_BORDER_WIDTH - MIN_BORDER_WIDTH) / max_depth,
    )


# ---------------------------------------------------------------------------
# Visualization — interactive HTML
# ---------------------------------------------------------------------------


def build_interactive_html(G: nx.DiGraph, output_path: Path):
    """Create a pyvis interactive HTML visualization of the graph."""
    net = Network(
        height="900px",
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="in_line",
        bgcolor="#FFFFFF",
        font_color="#333333",
        select_menu=False,
        filter_menu=False,
    )

    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "forceAtlas2Based": {
          "gravitationalConstant": -80,
          "centralGravity": 0.008,
          "springLength": 120,
          "springConstant": 0.06,
          "damping": 0.4,
          "avoidOverlap": 0.6
        },
        "solver": "forceAtlas2Based",
        "stabilization": {
          "enabled": true,
          "iterations": 1500,
          "updateInterval": 25
        },
        "maxVelocity": 50,
        "minVelocity": 0.01
      },
      "layout": {
        "improvedLayout": true,
        "randomSeed": 42
      },
      "edges": {
        "arrows": { "to": { "enabled": true, "scaleFactor": 0.5 } },
        "color": { "color": "#888888", "opacity": 0.5 },
        "smooth": { "type": "continuous" },
        "width": 1.2
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "zoomView": true,
        "dragView": true,
        "navigationButtons": true,
        "keyboard": { "enabled": true }
      }
    }
    """)

    depths = _compute_depths(G)
    max_depth = max(depths.values(), default=0)

    # Cluster seeds by model_category
    used_categories = sorted({G.nodes[n].get("model_category", "Other") for n in G.nodes})
    cat_to_index = {cat: i for i, cat in enumerate(used_categories)}
    n_cats = len(used_categories)
    CLUSTER_RADIUS = 600
    INTRA_SCATTER = 180
    _cat_counter: dict[str, int] = {c: 0 for c in used_categories}

    # Determine node sizes based on out-degree
    max_degree = max((G.out_degree(n) for n in G.nodes), default=1) or 1

    for node_id in G.nodes:
        data = G.nodes[node_id]
        label = data.get("label", node_id)
        model_cat = data.get("model_category", "Other")
        product = data.get("product", "General")
        tooltip = data.get("title", label)

        # Override color group to "Control" for control-related classes
        if CONTROL_NAME_PATTERNS.search(label):
            color_group = "Control"
        else:
            color_group = PRODUCT_TO_GROUP.get(product, "Other")
        color = GROUP_COLORS.get(color_group, "#BDBDBD")
        shape = CATEGORY_SHAPES_PYVIS.get(model_cat, "dot")
        bw = _border_width(depths.get(node_id, 0), max_depth)
        out_deg = G.out_degree(node_id)
        size = 18 + 27 * (out_deg / max_degree)

        # Compute initial position: cluster centre + spiral offset
        idx = cat_to_index.get(model_cat, 0)
        angle_base = 2 * math.pi * idx / max(n_cats, 1)
        cx = CLUSTER_RADIUS * math.cos(angle_base)
        cy = CLUSTER_RADIUS * math.sin(angle_base)
        seq = _cat_counter[model_cat]
        _cat_counter[model_cat] += 1
        spiral_angle = seq * 0.8
        spiral_r = INTRA_SCATTER * (0.3 + 0.7 * (seq / max(1, _cat_counter[model_cat])))
        x = cx + spiral_r * math.cos(spiral_angle)
        y = cy + spiral_r * math.sin(spiral_angle)

        net.add_node(
            node_id,
            label=label,
            title=tooltip,
            color={
                "background": color,
                "border": "#555555",
                "highlight": {"background": "#FF6B6B", "border": "#FF0000"},
                "hover": {"background": "#FFD700", "border": "#FF8C00"},
            },
            size=size,
            borderWidth=bw,
            shape=shape,
            font={"size": 14, "face": "Arial"},
            x=x,
            y=y,
        )

    for u, v in G.edges:
        net.add_edge(u, v)

    # --- Build legend HTML ---
    # Color groups: collect the actual group used for each node
    used_groups = set()
    for n in G.nodes:
        label_n = G.nodes[n].get("label", n)
        product_n = G.nodes[n].get("product", "General")
        if CONTROL_NAME_PATTERNS.search(label_n):
            used_groups.add("Control")
        else:
            used_groups.add(PRODUCT_TO_GROUP.get(product_n, "Other"))
    used_groups = sorted(used_groups)
    color_items = []
    for group in used_groups:
        c = GROUP_COLORS.get(group, "#BDBDBD")
        color_items.append(
            f'<span style="display:inline-block;width:14px;height:14px;'
            f"background:{c};border:1px solid #555;border-radius:3px;"
            f'margin-right:5px;vertical-align:middle;"></span>{group}'
        )
    color_legend = "<br>".join(color_items)

    # Model category shapes
    shape_labels = {
        "ellipse": "&#9711;",  # circle-like for Core
        "dot": "&#9679;",  # filled circle for Converter
        "diamond": "&#9670;",  # diamond for Storage
        "triangle": "&#9650;",  # triangle for Resource
        "star": "&#9733;",  # star for Finance
        "square": "&#9632;",  # square for Transporter
        "hexagon": "&#11042;",  # hexagon for Control
        "triangleDown": "&#9660;",  # down-triangle for Simulation
        "box": "&#9632;",  # square for Tools
    }
    used_cats = sorted({G.nodes[n].get("model_category", "Other") for n in G.nodes})
    shape_items = []
    for cat in used_cats:
        shape = CATEGORY_SHAPES_PYVIS.get(cat, "dot")
        symbol = shape_labels.get(shape, "&#9679;")
        shape_items.append(
            f'<span style="margin-right:5px;font-size:16px;vertical-align:middle;">'
            f"{symbol}</span>{cat}"
        )
    shape_legend = "<br>".join(shape_items)

    # Save and inject legend
    net.generate_html()
    raw_html = net.html
    output_path.write_text(raw_html, encoding="utf-8")
    html = output_path.read_text(encoding="utf-8")

    legend_div = f"""
    <div id="class-legend" style="
        position: fixed; top: 10px; right: 10px;
        background: rgba(255,255,255,0.95); border: 1px solid #ccc;
        border-radius: 8px; padding: 12px 16px;
        font-family: Arial, sans-serif; font-size: 13px;
        max-height: 90vh; overflow-y: auto;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        z-index: 9999; line-height: 1.8;
    ">
        <strong style="font-size:14px;">Color = Application Group</strong><br>
        {color_legend}
        <br><br>
        <strong style="font-size:14px;">Shape = Model Category</strong><br>
        {shape_legend}
        <br><br>
        <span style="font-size:11px;color:#888;">
            Border width = inheritance depth<br>
            (thicker = higher-level parent)<br><br>
            Arrows: parent &rarr; child<br>
            Scroll to zoom | Drag to pan
        </span>
    </div>
    """

    title_div = """
    <div style="
        position: fixed; top: 10px; left: 10px;
        background: rgba(255,255,255,0.95); border: 1px solid #ccc;
        border-radius: 8px; padding: 10px 18px;
        font-family: Arial, sans-serif;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        z-index: 9999;
    ">
        <strong style="font-size:18px;">H2Integrate Class Hierarchy</strong><br>
        <span style="font-size:12px;color:#666;">
            Interactive visualization &mdash; zoom, pan, hover for details
        </span>
    </div>
    """

    # Inject a script to disable physics after stabilization so the
    # diagram is still unless the user drags a node.
    stabilize_script = """
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        // vis.js stores the network on the container; poll until ready
        var check = setInterval(function() {
            if (typeof network !== "undefined" && network !== null) {
                clearInterval(check);
                network.once("stabilized", function() {
                    network.setOptions({ physics: { enabled: false } });
                });
                // Re-enable physics while dragging so connections stay sensible
                network.on("dragStart", function() {
                    network.setOptions({ physics: { enabled: true } });
                });
                network.on("dragEnd", function() {
                    network.setOptions({ physics: { enabled: false } });
                });
            }
        }, 200);
    });
    </script>
    """

    html = html.replace("</body>", f"{legend_div}\n{title_div}\n{stabilize_script}\n</body>")
    output_path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print(f"Scanning classes in {ROOT_DIR} ...")
    classes = scan_classes(ROOT_DIR)
    print(f"  Found {len(classes)} classes (excluding test files)")

    print("Building inheritance graph ...")
    G = build_graph(classes)
    print(f"  Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")

    # Remove isolated nodes (no inheritance relationships) to reduce clutter
    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)
    print(
        f"  After removing {len(isolates)} isolated classes: "
        f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
    )

    print(f"Generating interactive HTML → {OUTPUT_HTML} ...")
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    build_interactive_html(G, OUTPUT_HTML)

    print("Done!")

    # Print summary by category
    cats: dict[str, int] = {}
    for n in G.nodes:
        cat = G.nodes[n].get("model_category", "Other")
        cats[cat] = cats.get(cat, 0) + 1
    print("\nClasses by model category (in graph):")
    for cat in sorted(cats, key=cats.get, reverse=True):
        print(f"  {cat}: {cats[cat]}")


if __name__ == "__main__":
    main()
