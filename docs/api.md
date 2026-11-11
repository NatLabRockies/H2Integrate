# API Documentation

```{eval-rst}
.. currentmodule:: h2integrate

.. autosummary::
   :toctree: _autosummary
   :recursive:

   core
   feedstocks
   converters
   control
   finances
   resource
   storage
   transporters
   tools
   preprocess
   postprocess
   demand
   reliability
```

System-level controllers are in a namespace package and are listed explicitly so their modules
and classes are included in the API reference:

```{eval-rst}
.. currentmodule:: h2integrate.control.control_strategies.system_level

.. autosummary::
   :toctree: _autosummary

   system_level_control_baseclass
   solver_options
   demand_following_control
   cost_minimization_control
   profit_maximization_control
```
