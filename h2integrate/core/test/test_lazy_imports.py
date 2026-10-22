import sys
import pkgutil
import importlib
import subprocess

import pytest

import h2integrate
from h2integrate.core.lazy_imports import lazy_exports


def _lazy_packages():
    """Names of all packages whose ``__init__`` re-exports names lazily."""
    names = []
    for info in pkgutil.walk_packages(h2integrate.__path__, "h2integrate."):
        if info.ispkg and ".test" not in info.name:
            init_file = h2integrate.ROOT_DIR.joinpath(*info.name.split(".")[1:], "__init__.py")
            if "lazy_exports(" in init_file.read_text(encoding="utf-8"):
                names.append(info.name)
    return names


@pytest.mark.unit
def test_lazy_exports_behavior(subtests):
    namespace = {}
    getattr_, dir_ = lazy_exports("h2integrate.core", namespace, {"lazy_exports": "lazy_imports"})

    with subtests.test("unknown name raises AttributeError"):
        with pytest.raises(AttributeError, match="has no attribute 'missing'"):
            getattr_("missing")

    with subtests.test("dir lists exports before they are imported"):
        assert "lazy_exports" in dir_()
        assert "lazy_exports" not in namespace

    with subtests.test("exported name is imported and cached"):
        assert getattr_("lazy_exports") is lazy_exports
        assert namespace["lazy_exports"] is lazy_exports


@pytest.mark.unit
@pytest.mark.parametrize("package_name", _lazy_packages())
def test_lazy_package_exports_resolve(package_name):
    """Every name a package re-exports lazily must resolve to an object."""
    package = importlib.import_module(package_name)
    exported = [name for name in dir(package) if not name.startswith("_")]
    for name in exported:
        assert getattr(package, name) is not None


@pytest.mark.unit
def test_importing_package_does_not_import_submodules():
    code = (
        "import sys\n"
        "import h2integrate.converters.wind\n"
        "loaded = [m for m in sys.modules if m.startswith('h2integrate.converters.wind.')]\n"
        "assert not loaded, loaded\n"
        "from h2integrate.converters.wind import ATBWindPlantCostModel\n"
        "assert 'h2integrate.converters.wind.atb_wind_cost' in sys.modules\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
