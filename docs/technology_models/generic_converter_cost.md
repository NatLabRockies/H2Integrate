# Generic converter cost model

The {py:class}`~h2integrate.converters.generic_converter_cost.GenericConverterCostModel` estimates
converter costs from rated and annual production of a configurable commodity. Configure it with
{py:class}`~h2integrate.converters.generic_converter_cost.GenericConverterCostConfig`.
It supports one-hour time steps.

The model's configuration is:

```{eval-rst}
.. autoclass:: h2integrate.converters.generic_converter_cost.GenericConverterCostConfig
   :members:
   :no-index:
```

The model receives `rated_{commodity}_production` and `annual_{commodity}_produced`, along with
the cost coefficients and additional costs as OpenMDAO inputs. Depending on the selected fixed
cost method, it receives either `unit_opex` or `fixed_opex_ratio`. It reports:

- `CapEx`: rated production times `unit_capex`, plus `additional_constant_capex`.
- `OpEx`: rated production times `unit_opex`, or the capacity-scaled capital cost times
  `fixed_opex_ratio`, plus `additional_constant_opex`. The fraction does not apply to the
  additional constant capital cost.
- `VarOpEx`: annual production times `unit_varopex`, plus `additional_constant_varopex`, for each
  plant year.
