"""Tests for core file utilities."""

import pytest

from h2integrate.core.file_utils import load_component_config


@pytest.mark.unit
def test_load_component_config_validates_embedded_dictionary():
    config = {"value": 3}

    validated, file_path, parent_path = load_component_config(
        config,
        None,
        lambda value: {**value, "validated": True},
    )

    assert validated == {"value": 3, "validated": True}
    assert file_path is None
    assert parent_path is None


@pytest.mark.unit
def test_load_component_config_resolves_relative_to_main_config(tmp_path):
    main_config_path = tmp_path / "main.yaml"
    component_path = tmp_path / "component.yaml"
    main_config_path.touch()
    component_path.write_text("value: 3\n")

    validated, file_path, parent_path = load_component_config(
        component_path.name,
        main_config_path,
        lambda value: value,
    )

    assert validated == component_path.absolute()
    assert file_path == component_path.absolute()
    assert parent_path == tmp_path.absolute()
