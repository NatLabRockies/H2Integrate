import os
from importlib.metadata import version

from sphinx.config import Config
from sphinx.application import Sphinx


def configure_version_switcher(app: Sphinx, config: Config) -> None:
    readthedocs_version = os.environ.get("READTHEDOCS_VERSION", "latest")
    if readthedocs_version == "develop":
        readthedocs_version = "latest"

    theme_options = dict(config.html_theme_options or {})
    switcher_options = dict(theme_options.get("switcher", {}))
    switcher_options["version_match"] = readthedocs_version
    theme_options["switcher"] = switcher_options
    theme_options["announcement"] = f"H2Integrate {version('h2integrate')} documentation"
    config.html_theme_options = theme_options


def setup(app: Sphinx) -> dict[str, object]:
    app.connect("config-inited", configure_version_switcher)
    return {"version": "1.0", "parallel_read_safe": True}
