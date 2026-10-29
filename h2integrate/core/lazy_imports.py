"""Lazy re-exports for package ``__init__`` modules.

Importing a model module can be expensive (Ard, rex, and Pyomo each take seconds), so package
``__init__`` files must not import their submodules eagerly. They expose the same names through a
module-level ``__getattr__`` instead, and each submodule is imported on first access.
"""

import importlib

from h2integrate.core.supported_models import _model_exports


def lazy_exports(package_name, package_globals, extra_exports=None):
    """Build ``__getattr__`` and ``__dir__`` functions that import re-exported names on demand.

    Use in a package ``__init__.py`` as ``__getattr__, __dir__ = lazy_exports(__name__,
    globals())``. Registered models in the package are exported automatically.

    Args:
        package_name (str): Name of the package, usually ``__name__``.
        package_globals (dict): The package's ``globals()``, used to cache imported names.
        extra_exports (dict[str, str], optional): Non-model names mapped to their defining
            submodules, relative to the package (for example ``{"Foo": "foo_module"}``).

    Returns:
        tuple[Callable, Callable]: The module-level ``__getattr__`` and ``__dir__`` functions.
    """

    exports = {}
    for name, modules in _model_exports.get(package_name, {}).items():
        if len(modules) != 1:
            raise ValueError(f"Multiple modules export {name!r} in {package_name!r}: {modules}")
        exports[name] = modules[0]
    for name, submodule in (extra_exports or {}).items():
        if name in exports:
            raise ValueError(f"Duplicate export {name!r} in {package_name!r}")
        exports[name] = f"{package_name}.{submodule}"

    def __getattr__(name):
        if name not in exports:
            raise AttributeError(f"module {package_name!r} has no attribute {name!r}")
        module = importlib.import_module(exports[name])
        value = getattr(module, name)
        package_globals[name] = value
        return value

    def __dir__():
        return sorted({*package_globals, *exports})

    return __getattr__, __dir__
