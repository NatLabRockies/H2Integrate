import numpy as np
import pytest

from h2integrate.core.h2integrate_model import H2IntegrateModel


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("35_system_level_control/no_battery", None)]
)
def test_slc_no_battery(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "wind_ng_demand.yaml")

    model.run()

    wind_out = model.prob.get_val("wind.electricity_out")

    with subtests.test("wind farm generates power"):
        assert wind_out.sum() > 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder", [("35_system_level_control/yes_battery", None)]
)
def test_slc_yes_battery(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "wind_ng_demand.yaml")

    model.run()

    wind_out = model.prob.get_val("wind.electricity_out")

    with subtests.test("wind farm generates power"):
        assert wind_out.sum() > 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "example_folder,resource_example_folder",
    [("35_system_level_control/profit_maximization", None)],
)
def test_slc_profit_max(subtests, temp_copy_of_example):
    example_folder = temp_copy_of_example

    model = H2IntegrateModel(example_folder / "wind_ng_demand.yaml")

    n_timesteps = 8760
    sell_price = np.zeros(n_timesteps)
    for h in range(n_timesteps):
        hour_of_day = h % 24
        if 16 <= hour_of_day < 22:
            sell_price[h] = 0.08  # peak
        else:
            sell_price[h] = 0.03  # night (cheap)

    model.setup()

    model.prob.set_val(
        "plant.system_level_controller.commodity_sell_price",
        sell_price,
        units="USD/(kW*h)",
    )

    model.run()

    wind_out = model.prob.get_val("wind.electricity_out")

    with subtests.test("wind farm generates power"):
        assert wind_out.sum() > 0
