from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture_name", ["temp_copy_of_example", "temp_copy_of_example_module_scope"]
)
@pytest.mark.parametrize("example_folder,resource_example_folder", [("19_simple_dispatch", None)])
def test_example_fixture_restores_working_directory(
    request, monkeypatch, fixture_name, example_folder, resource_example_folder
):
    original_directory = Path.cwd()
    copied_example = request.getfixturevalue(fixture_name)

    assert Path.cwd() == copied_example
    assert copied_example != original_directory
    monkeypatch.undo()
    assert Path.cwd() == original_directory
