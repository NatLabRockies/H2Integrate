import numpy as np
import pytest
from attrs import field, define
from numpy import typing as npt

from h2integrate.core.array_validators import (
    array_ge,
    array_gt,
    array_le,
    array_lt,
    to_array,
    match_shape,
)


NDArrayFloat = npt.NDArray[np.float64]
NDArrayInt = npt.NDArray[np.int64]
NDArrayStr = npt.NDArray[np.str_]


@define
class ConverterConfig:
    int_arr: npt.ArrayLike = field(converter=to_array(int, (-1, 1)))
    float_arr: npt.ArrayLike = field(converter=to_array(float, (1, -1)))
    neg_int_arr: npt.ArrayLike = field(converter=to_array(int))
    neg_float_arr: npt.ArrayLike = field(converter=to_array(float))


@define
class ValidatorConfig:
    int_arr: npt.ArrayLike = field(converter=to_array(int, (-1, 1)), validator=array_ge(0))
    float_arr: npt.ArrayLike = field(converter=to_array(float, (1, -1)), validator=array_gt(0))
    neg_int_arr: npt.ArrayLike = field(converter=to_array(int), validator=array_lt(0))
    neg_float_arr: npt.ArrayLike = field(converter=to_array(float), validator=array_le(0))


@define
class ShapeValidatorConfig:
    field1: npt.ArrayLike = field(converter=to_array(int))
    field2: npt.ArrayLike = field(converter=to_array(int), validator=match_shape("field1"))


@pytest.mark.unit
def test_array_converter():
    """Tests ``array_converter``."""
    int_arr = [1, 2, 3, 4.2, 5.7]
    float_arr = [1, 2.1, 3.3]
    neg_int_arr = [-1, -2, -3, -4]
    neg_float_arr = [-1, -2.1, -3.3]
    demo = ConverterConfig(
        int_arr=int_arr, float_arr=float_arr, neg_int_arr=neg_int_arr, neg_float_arr=neg_float_arr
    )

    assert demo.int_arr.dtype is np.dtype(np.int64)
    assert demo.float_arr.dtype is np.dtype(np.float64)
    assert demo.neg_int_arr.dtype is np.dtype(np.int64)
    assert demo.neg_float_arr.dtype is np.dtype(np.float64)

    assert demo.int_arr.shape == (len(int_arr), 1)
    assert demo.float_arr.shape == (1, len(float_arr))
    assert demo.neg_int_arr.shape == (len(neg_int_arr),)
    assert demo.neg_float_arr.shape == (len(neg_float_arr),)

    assert (demo.int_arr == np.array([int(el) for el in int_arr]).reshape(-1, 1)).all()
    assert (demo.float_arr == np.array([float(el) for el in float_arr]).reshape(1, -1)).all()
    assert (demo.neg_int_arr == np.array([int(el) for el in neg_int_arr])).all()
    assert (demo.neg_float_arr == np.array([float(el) for el in neg_float_arr])).all()

    with pytest.raises(ValueError):
        ConverterConfig(["a", "2"], [1, 1], [1, 1], [1, 1])


@pytest.mark.unit
def test_array_value_limiting_validator(subtests):
    """Tests ``array_ge``, ``array_gt``, ``array_lt``, ``array_le``."""
    with subtests.test("Basic setup passes for value butting up against the validator value"):
        int_arr = [0, 1, 2, 3, 4257, -0.9]
        float_arr = [1, 2.1, 133, 1e-10]
        neg_int_arr = [-1, -2, -354]
        neg_float_arr = [0, -1, -1e-10, -33]
        ValidatorConfig(
            int_arr=int_arr,
            float_arr=float_arr,
            neg_int_arr=neg_int_arr,
            neg_float_arr=neg_float_arr,
        )

    with subtests.test("Non-inclusive checks fail at limit"):
        msg = "'float_arr' must have all values greater than 0."
        with pytest.raises(ValueError, match=msg):
            ValidatorConfig(int_arr=[0], float_arr=[0], neg_int_arr=[-1e-10], neg_float_arr=[0])

        msg = "'neg_int_arr' must have all values less than 0."
        with pytest.raises(ValueError, match=msg):
            ValidatorConfig(int_arr=[1], float_arr=[1e-10], neg_int_arr=[0], neg_float_arr=[-1])

    with subtests.test("Inclusive checks fail past limit"):
        msg = "'int_arr' must have all values greater than or equal to 0."
        with pytest.raises(ValueError, match=msg):
            ValidatorConfig(int_arr=[-1], float_arr=[10], neg_int_arr=[-10], neg_float_arr=[-10])

        msg = "'neg_float_arr' must have all values less than or equal to 0."
        with pytest.raises(ValueError, match=msg):
            ValidatorConfig(int_arr=[10], float_arr=[1], neg_int_arr=[-1], neg_float_arr=[1e-10])


@pytest.mark.unit
def test_match_shape_validator(subtests):
    """Tests ``match_shape``."""
    with subtests.test("Shapes match and pass"):
        demo = ShapeValidatorConfig(field1=[1, 2, 3], field2=[-1, -3, 20])
        assert demo.field1.shape == demo.field2.shape

    with subtests.test("Shapes don't match and fail"):
        msg = r"Shape of 'field2' \(4,\) does not match 'field1' \(3,\)."
        with pytest.raises(ValueError, match=msg):
            demo = ShapeValidatorConfig(field1=[1, 2, 3], field2=[-1, -3, 20, 2])
            assert demo.field1.shape == demo.field2.shape

        msg = r"Shape of 'field2' \(2,\) does not match 'field1' \(3,\)."
        with pytest.raises(ValueError, match=msg):
            demo = ShapeValidatorConfig(field1=[1, 2, 3], field2=[-1, 2])
            assert demo.field1.shape == demo.field2.shape
