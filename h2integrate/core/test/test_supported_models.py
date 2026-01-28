from h2integrate.core.supported_models import is_electricity_producer


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
