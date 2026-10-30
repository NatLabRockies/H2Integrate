import sys

import pytest
import openmdao.api as om

from h2integrate import H2IntegrateModel


def _recorder_model(output_folder, overwrite=False):
    return H2IntegrateModel(
        {
            "name": "recorder_test",
            "system_summary": "Grid model for recorder tests",
            "driver_config": {
                "name": "driver_config",
                "description": "Recorder test driver",
                "general": {"folder_output": str(output_folder), "create_om_reports": False},
                "recorder": {
                    "flag": True,
                    "file": "cases.sql",
                    "overwrite_recorder": overwrite,
                    "includes": ["grid.electricity_out"],
                },
            },
            "technology_config": {
                "name": "technology_config",
                "description": "Grid model",
                "technologies": {
                    "grid": {
                        "performance_model": {"model": "GridPerformanceModel"},
                        "model_inputs": {"shared_parameters": {"interconnection_size": 100.0}},
                    }
                },
            },
            "plant_config": {
                "name": "plant_config",
                "description": "Recorder test plant",
                "plant": {"plant_life": 1, "simulation": {"n_timesteps": 8760, "dt": 3600}},
            },
        }
    )


@pytest.mark.unit
def test_recorder_creates_unique_files(tmp_path, subtests):
    output_folder = tmp_path / "output"
    for filename in ("cases.sql", "cases0.sql", "cases1.sql"):
        with subtests.test(filename):
            model = _recorder_model(output_folder)
            path = output_folder / filename
            assert output_folder.is_dir()
            assert model.recorder_path == path
            assert not path.exists()
            model.run()
            assert path.is_file()
            assert list(om.CaseReader(str(path)).get_cases())
            model.prob.cleanup()


@pytest.mark.unit
@pytest.mark.xfail(sys.platform == "win32", reason="OpenMDAO incorrectly ends SQL processes")
def test_recorder_overwrites_existing_file(tmp_path):
    output_folder = tmp_path / "output"
    path = output_folder / "cases.sql"
    original = _recorder_model(output_folder)
    original.run()
    assert path.is_file()

    model = _recorder_model(output_folder, overwrite=True)
    assert model.recorder_path == path
    model.run()
    assert list(om.CaseReader(str(path)).get_cases())
    assert not (output_folder / "cases0.sql").exists()
    model.prob.cleanup()
