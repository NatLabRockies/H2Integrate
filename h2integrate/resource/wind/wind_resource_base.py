from openmdao.utils import units

from h2integrate.resource.resource_base import ResourceBaseAPIModel


class WindResourceBaseAPIModel(ResourceBaseAPIModel):
    def setup(self):
        super().setup()

        self.output_vars_to_units = {
            "wind_direction": "deg",
            "wind_speed": "m/s",
            "temperature": "degC",
            "pressure": "atm",
            "precipitation_rate": "mm/h",
            "relative_humidity": "percent",
            "is_day": "unitless",
        }

    def compare_units_and_correct(self, data, data_units):
        """Convert data to standard units defined in ``output_vars_to_units``.

        Note:
            The keys for `data` and `data_units` are expected to be formatted as
            `<var>_<height>m` where `var` is a key in the attribute ``output_vars_to_units``
            and `height` is the height of the data in meters.

        Note:
            the values for `data_units` must be formatted to be compatible with OpenMDAO units.

        Args:
            data (dict): dictionary of data, keys are data names and values may be
                a scalar or array of numerical values in units of ``data_units[data_key]``.
            data_units (dict): dictionary of units corresponding to the data.
                Has the same keys as `data` with values as a str of OpenMDAO compatible units.

        Raises:
            Warning: if a key in `data` does not contain any key in the attribute
                ``output_vars_to_units``.
            Warning: if a key in `data` contains multiple keys in the attribute
                ``output_vars_to_units``.

        Returns:
            2-element tuple containing

            - **data** (*dict*): data converted to standard units found in the attribute
                ``output_vars_to_units``.
            - **data_units** (*dict*): updated units of data in ``data``.
        """
        for data_col, orig_units in data_units.items():
            output_var = [k for k in self.output_vars_to_units if k in data_col]
            if len(output_var) == 1:
                desired_units = self.output_vars_to_units[output_var[0]]
                if desired_units != orig_units:
                    data[data_col] = units.convert_units(data[data_col], orig_units, desired_units)
                    data_units[data_col] = desired_units
            else:
                if len(output_var) < 1:
                    raise Warning(f"{data_col} not found as common variable.")
                else:
                    raise Warning(f"{data_col} not found as a unique common variable.")
        return data, data_units
