import numpy as np
import pytest

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
