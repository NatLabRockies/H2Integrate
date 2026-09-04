import numpy as np
import pytest

from h2integrate.reliability.models import SimulationConfig
from h2integrate.reliability.utilities import update_dimensions


@pytest.mark.unit
def test_update_dimensions(subtests):
    """Tests ``update_dimensions``."""
    with subtests.test("n_components is updated to array size"):
        arr = np.array([1, 2, 3])
        n_components, new_arr = update_dimensions(2, arr)

        assert n_components == len(arr)
        np.testing.assert_array_equal(new_arr, arr)

    with subtests.test("arrays are updated to n_components number of rows"):
        arr1 = np.array([[1]])
        arr2 = np.array([[3]])
        n_components = 3
        new_n_components, new_arr1, new_arr2 = update_dimensions(n_components, arr1, arr2)

        assert new_n_components == n_components
        assert new_arr1.shape == (n_components, 1)
        assert (new_arr1 == 1).all()
        assert new_arr2.shape == (n_components, 1)
        assert (new_arr2 == 3).all()


@pytest.mark.unit
def test_simulation_calculations(subtests):
    """Tests ``calculate_simulation_years``, ``calculate_annual_timesteps``, and
    ``calculate_hourly_timesteps``.
    """
    with subtests.test("Hourly simulation, single year"):
        sim = SimulationConfig(dt=3600, n_timesteps=8760)
        assert sim.n_timesteps_in_year == 8760
        assert sim.n_timesteps_in_hour == 1
        assert sim.simulation_years == 1

    with subtests.test("Hourly simulation, two years"):
        sim = SimulationConfig(dt=3600, n_timesteps=8760 * 2)
        assert sim.n_timesteps_in_year == 8760
        assert sim.n_timesteps_in_hour == 1
        assert sim.simulation_years == 2

    with subtests.test("Minutely simulation, half a year"):
        sim = SimulationConfig(dt=60, n_timesteps=8760 * 60 / 2)
        assert sim.n_timesteps_in_year == 8760 * 60
        assert sim.n_timesteps_in_hour == 60
        assert sim.simulation_years == 0.5
