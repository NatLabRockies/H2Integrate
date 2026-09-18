"""Tests for OpenMDAO result reporting utilities."""

import numpy as np
import pytest

from h2integrate.postprocess.reporting import print_results


class _FakeModel:
    def __init__(self):
        self.output_calls = []
        self.input_call = None

    def list_outputs(self, **kwargs):
        self.output_calls.append(kwargs)
        if kwargs["explicit"]:
            return [
                (
                    "plant.tech.power_out",
                    {
                        "val": np.array([2.0, 4.0]),
                        "units": "kW",
                        "shape": (2,),
                        "prom_name": "tech.power_out",
                    },
                )
            ]
        return []

    def list_inputs(self, **kwargs):
        self.input_call = kwargs
        return [
            (
                "plant.tech.cost_year",
                {
                    "val": 2030,
                    "units": "year",
                    "shape": (1,),
                    "prom_name": "tech.cost_year",
                },
            )
        ]


@pytest.mark.unit
def test_print_results_returns_structured_summary_and_forwards_filters():
    model = _FakeModel()

    result = print_results(
        model,
        includes=["plant.*"],
        excludes=["*resource_data"],
    )

    assert result["inputs"]["plant.tech.cost_year"] == {
        "mean": "2030",
        "units": "n/a",
        "shape": "n/a",
        "promoted_name": "tech.cost_year",
    }
    assert result["explicit_outputs"]["plant.tech.power_out"] == {
        "mean": "3.0",
        "units": "kW",
        "shape": 2,
        "promoted_name": "tech.power_out",
    }
    assert result["implicit_outputs"] == {}
    assert model.input_call["includes"] == ["plant.*"]
    assert model.input_call["excludes"] == ["*resource_data"]
    assert all(call["out_stream"] is None for call in model.output_calls)


@pytest.mark.unit
def test_print_results_can_omit_units():
    result = print_results(_FakeModel(), show_units=False)

    assert "units" not in result["inputs"]["plant.tech.cost_year"]
    assert "units" not in result["explicit_outputs"]["plant.tech.power_out"]
