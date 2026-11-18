"""Sphinx configuration file.
For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

import sys
from pathlib import Path
from importlib.metadata import version as find_version


DOCS = Path(__file__).parent
sys.path.insert(0, DOCS)

# -- Project information ---------------------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "H2Integrate"
copyright = "2026, Alliance for Energy Innovation, LLC"  # noqa: A001
author = "NLR"

release = ".".join(find_version("h2integrate").split(".")[:2])
version = find_version("h2integrate")

# -- General configuration -------------------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

master_doc = "index"
language = "en"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinx.ext.ifconfig",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.autosummary",
    "sphinx.ext.autosectionlabel",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinxcontrib.bibtex",
    "sphinx_gallery.gen_gallery",
    "myst_nb",  # NOTE: encapsulates myst_parser
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "markdown",
    ".ipynb": "myst-nb",
    ".md": "myst-nb",
}

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "jupyter_execute"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False


# -- Options for HTML output -----------------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_css_files = [
    "css/custom.css",
]
html_theme_options = {
    "github_url": "https://github.com/NatLabRockies/H2Integrate",
    "navbar_start": ["navbar-logo"],
    "show_toc_level": 1,
    "show_nav_level": 3,
    "navigation_depth": 4,
    "collapse_navigation": True,
    "use_edit_page_button": True,
    "navbar_align": "left",
    "logo": {"image_light": "", "image_dark": ""},
}

html_context = {
    "default_mode": "light",
    "github_url": "https://github.com/",
    "github_user": "NatLabRockies",
    "github_repo": "H2Integrate",
    "github_version": "develop",
    "doc_path": "docs",
}

html_static_path = ["_static"]
bibtex_bibfiles = ["refs.bib"]


# -- Options for Autodoc ---------------------------------------------------------------------------

autodoc_typehints = "both"
autodoc_default_options = {
    "autoclass_content": "class",
    "member-order": "bysource",
    "members": True,
}

# with (DOCS.parent / "pyproject.toml").open("rb") as f:
#     data = tomllib.load(f)

# exclude_deps = ("all", "examples", "develop", "extras")
# optional_deps = [
#     val for key, val in data["project"]["optional-dependencies"].items() if key not in exclude_deps  # noqa: E501
# ]
# optional_deps = [
#     el for el in itertools.chain.from_iterable(optional_deps) if "h2integrate" not in el
# ]
# autodoc_mock_imports = [*data["project"]["dependencies"], *optional_deps]


# -- Options for Myst ------------------------------------------------------------------------------

# Syntax descriptions and examples:
# https://myst-parser.readthedocs.io/en/latest/syntax/optional.html#syntax-extensions
myst_enable_extensions = [
    "amsmath",
    # "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    # "html_image",
    "linkify",  # linkify-it-py
    # "replacements",
    # "smartquotes",
    # "strikethrough",
    # "substitution",
    "tasklist",
]

# toggle this between auto/off to rerun full documentation build
nb_execution_mode = "cache"  # Should be coming from the examples folder
nb_execution_excludepatterns = ["examples/*"]
nb_merge_streams = True
nb_execution_cache_path = "_build/.jupyter_cache"
nb_render_markdown_format = "myst"

myst_heading_anchors = 3


# -- Options for Napolean --------------------------------------------------------------------------

napoleon_google_docstring = True
napoleon_use_param = False
napoleon_use_ivar = False
autoclass_content = "both"


# -- Options for Napolean --------------------------------------------------------------------------

sphinx_gallery_conf = {
    "examples_dirs": "../examples",
    "gallery_dirs": "auto_examples",  # gallery generated output
}
