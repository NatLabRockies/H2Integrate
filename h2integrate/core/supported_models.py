"""Registry of the models that can be referenced by name in H2Integrate configuration files.

Models are registered with the :func:`register` class decorator. To keep imports fast, decorated
classes are found by scanning the package source as text, and each model's module is only imported
the first time that model is looked up.
"""

import re
import importlib
from pathlib import Path


_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_DECORATED_CLASS = re.compile(
    r"^@register(?:\((?P<args>[^)]*)\))?\s+class (?P<cls>\w+)", re.MULTILINE
)
_NAME_ARG = re.compile(r"name\s*=\s*[\"'](\w+)[\"']")


def register(cls=None, *, name=None, no_cost=False, no_replacement_schedule=False):
    """Mark a class as an H2Integrate model.

    This is a marker only: the registry reads it from the source, so it must be at column 0,
    directly above the ``class`` line, with literal arguments.

    Args:
        name (str, optional): Name used in configuration files. Defaults to the class name.
        no_cost (bool, optional): The model does not contribute costs to the finance stackup.
        no_replacement_schedule (bool, optional): The model has no ``replacement_schedule``
            output for system-level finance models.
    """
    return cls if cls is not None else (lambda model_cls: model_cls)


class _ModelRegistry(dict):
    """Dict of model names to classes that imports each class on first access."""

    def __getitem__(self, name):
        value = super().__getitem__(name)
        if isinstance(value, str):
            module_name, class_name = value.split(":")
            value = getattr(importlib.import_module(module_name), class_name)
            self[name] = value
        return value

    def get(self, name, default=None):
        return self[name] if name in self else default

    def copy(self):
        return _ModelRegistry(super().copy())


supported_models = _ModelRegistry()
no_cost_models = set()
no_replacement_schedule_models = set()

for path in _PACKAGE_DIR.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    if "@register" not in text or "test" in path.relative_to(_PACKAGE_DIR).parts:
        continue
    module = ".".join(path.relative_to(_PACKAGE_DIR.parent).with_suffix("").parts)
    for match in _DECORATED_CLASS.finditer(text):
        args = match["args"] or ""
        name_match = _NAME_ARG.search(args)
        name = name_match[1] if name_match else match["cls"]
        if name in supported_models:
            raise ValueError(f"Model name '{name}' is registered more than once.")
        supported_models[name] = f"{module.removesuffix('.__init__')}:{match['cls']}"
        if "no_cost=True" in args:
            no_cost_models.add(name)
        if "no_replacement_schedule=True" in args:
            no_replacement_schedule_models.add(name)
