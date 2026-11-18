import re
import ast
from pathlib import Path

import pytest


@pytest.mark.unit
def test_configuration_docstrings_cover_declared_fields():
    """Require each configuration class to document its declared fields."""
    package_dir = Path(__file__).parents[2]
    missing_fields = []

    for path in package_dir.rglob("*.py"):
        if "test" in path.parts:
            continue

        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if not isinstance(node, ast.ClassDef) or not node.name.endswith("Config"):
                continue

            fields = [
                statement.target.id
                for statement in node.body
                if isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and not statement.target.id.startswith("_")
            ]
            if not fields:
                continue

            docstring = ast.get_docstring(node) or ""
            documented_fields = set()
            lines = docstring.splitlines()
            for index, line in enumerate(lines):
                if line.strip() != "Attributes:":
                    continue
                for attribute_line in lines[index + 1 :]:
                    if attribute_line and not attribute_line.startswith(" "):
                        break
                    match = re.match(r" {4}([A-Za-z_]\w*)\s*(?:\(|:)", attribute_line)
                    if match:
                        documented_fields.add(match.group(1))

            missing_fields.extend(
                f"{path.relative_to(package_dir)}:{node.lineno} {node.name}.{field}"
                for field in fields
                if field not in documented_fields
            )

    message = "Configuration fields missing from Attributes docstrings:\n" + "\n".join(
        missing_fields
    )
    assert not missing_fields, message
