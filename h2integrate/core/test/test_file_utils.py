"""Tests for core file utilities."""

import pytest

from h2integrate.core.file_utils import load_component_config, check_file_format_for_csv_generator


CSV_ROWS = "25000.0,5.0\n50000.0,10.0\n"
DRIVER_CONFIG = {
    "design_variables": {
        "solar": {"system_capacity_DC": {"flag": True}, "tilt": {"flag": False}},
        "electrolyzer": {"n_clusters": {"flag": True}},
    }
}


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


@pytest.mark.unit
def test_csv_generator_check_accepts_valid_file(tmp_path):
    csv_fpath = tmp_path / "cases.csv"
    csv_fpath.write_text("solar.system_capacity_DC,electrolyzer.n_clusters\n" + CSV_ROWS)

    assert check_file_format_for_csv_generator(csv_fpath, DRIVER_CONFIG) is True
    assert (
        check_file_format_for_csv_generator(csv_fpath, DRIVER_CONFIG, check_only=False) == csv_fpath
    )


@pytest.mark.unit
def test_csv_generator_check_removes_byte_order_mark(subtests, tmp_path):
    csv_fpath = tmp_path / "cases.csv"
    original_bytes = (
        b"\xef\xbb\xbfsolar.system_capacity_DC,electrolyzer.n_clusters\n" + CSV_ROWS.encode()
    )
    csv_fpath.write_bytes(original_bytes)

    with subtests.test("Check only reports the formatting issue"):
        assert check_file_format_for_csv_generator(csv_fpath, DRIVER_CONFIG) is False

    new_fpath = check_file_format_for_csv_generator(csv_fpath, DRIVER_CONFIG, check_only=False)

    with subtests.test("Fixed file is written next to the original with a unique name"):
        assert new_fpath == tmp_path / "cases0.csv"
        assert csv_fpath.read_bytes() == original_bytes

    with subtests.test("Fixed file has a clean header and unchanged rows"):
        assert new_fpath.read_text() == (
            "solar.system_capacity_DC,electrolyzer.n_clusters\n" + CSV_ROWS
        )
        assert check_file_format_for_csv_generator(new_fpath, DRIVER_CONFIG) is True


@pytest.mark.unit
def test_csv_generator_check_overwrites_file(tmp_path):
    csv_fpath = tmp_path / "cases.csv"
    csv_fpath.write_bytes(
        b"\xef\xbb\xbfsolar.system_capacity_DC,electrolyzer.n_clusters\n" + CSV_ROWS.encode()
    )

    new_fpath = check_file_format_for_csv_generator(
        csv_fpath, DRIVER_CONFIG, check_only=False, overwrite_file=True
    )

    assert new_fpath == csv_fpath.absolute()
    assert check_file_format_for_csv_generator(csv_fpath, DRIVER_CONFIG) is True
    assert list(tmp_path.iterdir()) == [csv_fpath]


@pytest.mark.unit
def test_csv_generator_check_removes_index_column(tmp_path):
    csv_fpath = tmp_path / "cases.csv"
    csv_fpath.write_text(
        ",solar.system_capacity_DC,electrolyzer.n_clusters\n0,25000.0,5.0\n1,50000.0,10.0\n"
    )

    new_fpath = check_file_format_for_csv_generator(csv_fpath, DRIVER_CONFIG, check_only=False)

    assert new_fpath.read_text() == "solar.system_capacity_DC,electrolyzer.n_clusters\n" + CSV_ROWS


@pytest.mark.unit
@pytest.mark.parametrize(
    "column,message",
    [
        ("solar.tilt", "is an invalid design variable"),
        ("solar.system_capacity_DCelectrolyzer.n_clusters", "does not match a unique"),
    ],
    ids=["inactive_design_variable", "ambiguous_column"],
)
def test_csv_generator_check_rejects_invalid_columns(tmp_path, column, message):
    csv_fpath = tmp_path / "cases.csv"
    csv_fpath.write_text(f"solar.system_capacity_DC,{column}\n" + CSV_ROWS)

    assert check_file_format_for_csv_generator(csv_fpath, DRIVER_CONFIG) is False
    with pytest.raises(ValueError, match=message):
        check_file_format_for_csv_generator(csv_fpath, DRIVER_CONFIG, check_only=False)
