"""
Generate an interactive class hierarchy visualization for H2Integrate.

This script scans the h2integrate package to discover all classes and their
inheritance relationships, then produces an interactive HTML visualization
(zoomable and scrollable) suitable for embedding in the Jupyter Book docs.

Usage:
    python generate_class_hierarchy.py

Outputs:
    docs/developer_guide/class_hierarchy.html  — interactive graph
"""

import os
import re
import ast
from pathlib import Path

import networkx as nx
from pyvis.network import Network


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Root of the h2integrate package
REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "h2integrate"
OUTPUT_HTML = REPO_ROOT / "docs" / "_static" / "class_hierarchy.html"

# Directories / path fragments that indicate test code (case-insensitive check)
TEST_INDICATORS = {"test", "tests", "conftest", "test_"}

# We only show H2I-native classes; external bases (OpenMDAO, attrs, etc.)
# are excluded from the visualization entirely.
EXTERNAL_BASES_TO_KEEP: set[str] = set()

# Category detection rules: (directory substring -> category label)
# Order matters — first match wins.
CATEGORY_RULES = [
    ("core", "Core / Base"),
    ("converters/hydrogen", "Converter - Hydrogen"),
    ("converters/ammonia", "Converter - Ammonia"),
    ("converters/iron", "Converter - Iron"),
    ("converters/steel", "Converter - Steel"),
    ("converters/methanol", "Converter - Methanol"),
    ("converters/wind", "Converter - Wind"),
    ("converters/solar", "Converter - Solar"),
    ("converters/nuclear", "Converter - Nuclear"),
    ("converters/grid", "Converter - Grid"),
    ("converters/water_power", "Converter - Water Power"),
    ("converters/water", "Converter - Water"),
    ("converters/natural_gas", "Converter - Natural Gas"),
    ("converters/nitrogen", "Converter - Nitrogen"),
    ("converters/co2", "Converter - CO2"),
    ("converters/hopp", "Converter - HOPP"),
    ("converters", "Converter - Other"),
    ("storage", "Storage"),
    ("resource", "Resource"),
    ("finances", "Finance"),
    ("transporters", "Transporter"),
    ("control", "Control"),
    ("simulation", "Simulation"),
    ("tools", "Tools / Utilities"),
    ("postprocess", "Post-processing"),
    ("preprocess", "Pre-processing"),
]

# Color palette for categories (soft, accessible colors)
CATEGORY_COLORS = {
    "Core / Base": "#6C8EBF",  # Steel blue
    "Converter - Hydrogen": "#82B366",  # Green
    "Converter - Ammonia": "#B3D987",  # Light green
    "Converter - Iron": "#D4A373",  # Tan / brown
    "Converter - Steel": "#C9A96E",  # Gold-brown
    "Converter - Methanol": "#E6B8A2",  # Salmon
    "Converter - Wind": "#97C2D9",  # Sky blue
    "Converter - Solar": "#FFD966",  # Sunny yellow
    "Converter - Nuclear": "#D5A6BD",  # Mauve
    "Converter - Grid": "#A4C2A5",  # Sage green
    "Converter - Water Power": "#7EB6D9",  # Ocean blue
    "Converter - Water": "#89CFF0",  # Baby blue
    "Converter - Natural Gas": "#E8C07A",  # Warm gold
    "Converter - Nitrogen": "#B5B5E6",  # Lavender
    "Converter - CO2": "#C4C4C4",  # Gray
    "Converter - HOPP": "#AAD4AA",  # Mint
    "Converter - Other": "#B8D4A8",  # Light sage
    "Storage": "#D79B00",  # Amber / orange
    "Resource": "#9673A6",  # Purple
    "Finance": "#DA70D6",  # Orchid
    "Transporter": "#FF8C69",  # Salmon-orange
    "Control": "#6FA8DC",  # Cornflower blue
    "Simulation": "#76A5AF",  # Teal
    "Tools / Utilities": "#999999",  # Gray
    "Post-processing": "#AAAAAA",  # Light gray
    "Pre-processing": "#BBBBBB",  # Lighter gray
    "External": "#E0E0E0",  # Very light gray
}

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


def _relative_module_path(filepath: Path) -> str:
    """Return the filepath relative to the repo root using forward slashes."""
    try:
        return str(filepath.relative_to(PACKAGE_ROOT)).replace("\\", "/")
    except ValueError:
        return str(filepath).replace("\\", "/")


def _classify(filepath: Path) -> str:
    """Determine the category for a class based on its file path."""
    rel = _relative_module_path(filepath)
    for pattern, category in CATEGORY_RULES:
        if pattern in rel:
            return category
    return "Other"


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
                raw.append(
                    {
                        "name": node.name,
                        "bases": bases,
                        "file": filepath,
                        "category": _classify(filepath),
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
            module = _relative_module_path(r["file"]).replace("/", ".").removesuffix(".py")
            key = f"{module}.{name}"
        else:
            key = name
        classes[key] = {
            "bases": r["bases"],
            "file": r["file"],
            "category": r["category"],
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
        G.add_node(
            key,
            label=short_name,
            category=info["category"],
            title=f"{short_name}\n{_relative_module_path(info['file'])}",
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
# Visualization
# ---------------------------------------------------------------------------


def build_interactive_html(G: nx.DiGraph, output_path: Path):
    """Create a pyvis interactive HTML visualization of the graph."""
    net = Network(
        height="900px",
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="in_line",  # self-contained HTML
        bgcolor="#FFFFFF",
        font_color="#333333",
        select_menu=False,
        filter_menu=False,
    )

    # Physics: force-directed layout for an organic "word cloud" / blob feel.
    # Categories naturally cluster because they share common parents.
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
          "iterations": 800,
          "updateInterval": 25
        },
        "maxVelocity": 50,
        "minVelocity": 0.75
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

    # Determine node sizes based on out-degree (more children = larger)
    max_degree = max((G.out_degree(n) for n in G.nodes), default=1) or 1

    # --- Assign initial (x, y) positions so same-category nodes start near
    #     each other.  The physics engine will refine from here, but the
    #     cluster seeds keep like-colored groups together.
    import math

    used_categories = sorted({G.nodes[n].get("category", "Other") for n in G.nodes})
    cat_to_index = {cat: i for i, cat in enumerate(used_categories)}
    n_cats = len(used_categories)
    CLUSTER_RADIUS = 600  # distance of cluster centres from origin
    INTRA_SCATTER = 180  # jitter within a cluster

    # Count how many nodes each category has so far (for spiral placement)
    _cat_counter: dict[str, int] = {c: 0 for c in used_categories}

    for node_id in G.nodes:
        data = G.nodes[node_id]
        label = data.get("label", node_id)
        category = data.get("category", "Other")
        color = CATEGORY_COLORS.get(category, "#CCCCCC")
        tooltip = data.get("title", label)
        out_deg = G.out_degree(node_id)

        # Scale node size: base 18, up to 45 for the most-connected nodes
        size = 18 + 27 * (out_deg / max_degree)

        # Slightly bolder border for base/core classes
        border_width = 3 if category == "Core / Base" else 1

        shape = "dot"

        # Compute initial position: cluster centre + spiral offset
        idx = cat_to_index.get(category, 0)
        angle_base = 2 * math.pi * idx / n_cats
        cx = CLUSTER_RADIUS * math.cos(angle_base)
        cy = CLUSTER_RADIUS * math.sin(angle_base)
        seq = _cat_counter[category]
        _cat_counter[category] += 1
        spiral_angle = seq * 0.8
        spiral_r = INTRA_SCATTER * (0.3 + 0.7 * (seq / max(1, _cat_counter[category])))
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
            borderWidth=border_width,
            shape=shape,
            font={"size": 14, "face": "Arial"},
            x=x,
            y=y,
        )

    for u, v in G.edges:
        net.add_edge(u, v)

    # Build a legend as an HTML overlay
    legend_items = []
    # Collect only categories actually used
    used_cats = sorted({G.nodes[n].get("category", "Other") for n in G.nodes})
    for cat in used_cats:
        c = CATEGORY_COLORS.get(cat, "#CCCCCC")
        legend_items.append(
            f'<span style="display:inline-block;width:14px;height:14px;'
            f"background:{c};border:1px solid #555;border-radius:3px;"
            f'margin-right:5px;vertical-align:middle;"></span>{cat}'
        )
    legend_html = "<br>".join(legend_items)

    # Save raw HTML first, then inject the legend.
    # Use generate_html() + manual write to ensure UTF-8 encoding on Windows.
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
        <strong style="font-size:14px;">Category Legend</strong><br>
        {legend_html}
        <br><br>
        <span style="font-size:11px;color:#888;">
            Arrows: parent -> child<br>
            Scroll to zoom | Drag to pan | Click to select
        </span>
    </div>
    """

    # Also add a title banner
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
            Interactive visualization — zoom, pan, hover for details
        </span>
    </div>
    """

    # Inject before closing </body>
    html = html.replace("</body>", f"{legend_div}\n{title_div}\n</body>")
    output_path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print(f"Scanning classes in {PACKAGE_ROOT} ...")
    classes = scan_classes(PACKAGE_ROOT)
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

    print("Done! Open the HTML file in a browser to explore the class hierarchy.")

    # Print summary by category
    cats: dict[str, int] = {}
    for n in G.nodes:
        cat = G.nodes[n].get("category", "Other")
        cats[cat] = cats.get(cat, 0) + 1
    print("\nClasses by category (in graph):")
    for cat in sorted(cats, key=cats.get, reverse=True):
        print(f"  {cat}: {cats[cat]}")


if __name__ == "__main__":
    main()
