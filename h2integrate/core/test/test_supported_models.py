from h2integrate.core.supported_models import supported_models, is_electricity_producer


def test_is_electricity_producer(subtests):
    with subtests.test("exact match"):
        assert is_electricity_producer("grid_buy")

    with subtests.test("partial starts-with match"):
        assert is_electricity_producer("grid_buy_1")

    with subtests.test("partial ends-with match fails"):
        assert not is_electricity_producer("wrong_grid_buy")

    with subtests.test("empty string fails"):
        assert not is_electricity_producer("")

    with subtests.test("non-electricity producing tech fails"):
        assert not is_electricity_producer("battery")


def test_dictionary_mapping():
    """Tests that the supported_models dictionary keys exactly match the model class name,
    except for allowed transport models that simplify configuration readability.
    """
    allowed_mismatch = ("cable", "pipe")
    mismatches = {k for k, v in supported_models.items() if k != v.__name__}
    mismatches = mismatches.difference(allowed_mismatch)
    assert len(mismatches) == 0, f"Model dictionary keys don't match their class name: {mismatches}"
