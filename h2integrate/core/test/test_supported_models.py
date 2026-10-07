import pytest

from h2integrate.core.supported_models import (
    _ModelRegistry,
    no_cost_models,
    supported_models,
    no_replacement_schedule_models,
)


@pytest.mark.unit
def test_supported_models(subtests):
    with subtests.test("entries are imported on first lookup"):
        registry = _ModelRegistry({"Grid": "h2integrate.converters.grid.grid:GridPerformanceModel"})
        registry_copy = registry.copy()
        assert registry_copy["Grid"].__name__ == "GridPerformanceModel"
        assert isinstance(dict.__getitem__(registry, "Grid"), str)
        assert registry.get("missing") is None

    with subtests.test("name argument"):
        assert supported_models["cable"].__name__ == "CablePerformanceModel"
        assert supported_models["pipe"].__name__ == "PipePerformanceModel"

    with subtests.test("flags"):
        assert no_cost_models == {
            "cable",
            "pipe",
            "GenericSplitterPerformanceModel",
            "GenericCombinerPerformanceModel",
            "GasStreamCombinerPerformanceModel",
            "GenericTransporterPerformanceModel",
        }
        assert no_replacement_schedule_models == {
            "IronTransportPerformanceComponent",
            "GenericTransporterPerformanceModel",
        }
