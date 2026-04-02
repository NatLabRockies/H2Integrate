import pytest

from h2integrate.core.supported_models import supported_models


@pytest.mark.unit
def test_dictionary_mapping():
    """Tests that the supported_models dictionary keys exactly match the model class name,
    except for allowed transport models that simplify configuration readability.
    """
    allowed_mismatch = ("cable", "pipe")
    mismatches = {k for k, v in supported_models.items() if k != v.__name__}
    mismatches = mismatches.difference(allowed_mismatch)
    assert len(mismatches) == 0, f"Model dictionary keys don't match their class name: {mismatches}"
