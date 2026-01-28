# Design optimization in H2I

One of the key features of H2Integrate is the ability to perform design optimization for hybrid energy systems.
This is done by using the [OpenMDAO framework](https://openmdao.org/), which allows for the optimization of complex systems with multiple components and interactions.

The design optimization process uses the `driver_config.yaml` file to define the optimization problem, including the design variables, constraints, and objective functions.
This doc page will walk you through the steps to set up a design optimization problem in H2Integrate.
We will lean on the `05_wind_h2_opt` example in the `examples` folder to illustrate the process.

```{note}
When we say "driver" in this context, we are referring to the optimizer that is used to solve the optimization problem as detailed in this [OpenMDAO doc page](https://openmdao.org/newdocs/versions/latest/basic_user_guide/single_disciplinary_optimization/first_optimization.html).
Drivers could also refer to a design of experiments (DOE) or other types of analysis that are not strictly optimizers.
```


## Driver config file

The driver config file defines the analysis type and the optimization settings.
If you are running a basic analysis and not an optimization, the driver config file is quite straightforward.
However, if you are running an optimization, the driver config file will contain additional top-level keys to define the optimization settings, including driver specifications, design variables, constraints, and objective functions.

For completeness, here is an example of a driver config file for a design optimization problem:

```yaml
name: "driver_config"
description: "Runs a wind plant and electrolyzer with simple optimization"

general:
  folder_output: wind_plant_run

driver:
  optimization:
    flag: True
    tol: 0.1
    max_iter: 100
    solver: COBYLA
    rhobeg: 500.
    debug_print: True

design_variables:
  electrolyzer:
    electrolyzer_size_mw:
      flag: True
      lower: 200
      upper: 1800.
      units: MW

constraints:
  electrolyzer:
    total_hydrogen_produced:
      flag: True
      lower: 60500000.
      units: kg/year

objective:
  name: finance_subgroup_default.LCOH
```

```{note}
We currently only support continuous design variables and constraints in H2Integrate.
Integer design variables, such as the number of wind turbines, are not supported at this time.
```

## Driver specifications

The `driver` section of the driver config file defines the optimization settings.
The `optimization` key is a dictionary that details key optimization settings, including the following:
- `flag`: A boolean flag that indicates whether the optimization is enabled or not. If set to `True`, the optimization will be performed.
- `tol`: The tolerance for the optimization. This is the stopping criterion for the optimization algorithm.
- `max_iter`: The maximum number of iterations for the optimization algorithm.
- `solver`: The optimization algorithm to use. H2Integrate supports several solvers, including `COBYLA`, `SLSQP`, and the proprietary code `SNOPT`.
- `rhobeg`: The initial size of the trust region for the optimization algorithm.
- `debug_print`: A boolean flag that indicates whether to print debug information during the optimization process.

This is not an exhaustive list of the driver specifications, but it covers the most common ones.
Different drivers may have different options available, so be sure to check the documentation for the specific driver you are using.
Both the [OpenMDAO docs on drivers](https://openmdao.org/newdocs/versions/latest/features/building_blocks/drivers/index.html) as well as the internal source code in H2I for the optimization driver can be helpful in understanding the options available to you.

## Design variables

The `design_variables` section of the driver config file defines the design variables for the optimization problem.
Any input to a component in H2I that is exposed to OpenMDAO can be a design variable.
Each technology in the analysis can have its own set of design variables, which are defined under the technology name.
The design variables are defined as a dictionary, where the keys are the names of the design variables and the values are dictionaries that define the properties of each design variable.

In the example above, we have a single design variable, `electrolyzer_size_mw`, which is the size of the electrolyzer in megawatts (MW).
We define the following properties for this design variable:
- `flag`: A boolean flag that indicates whether the design variable is enabled or not. If set to `True`, the design variable will be included in the optimization problem.
- `lower`: The lower bound for the design variable. This is the minimum value that the design variable can take during the optimization process.
- `upper`: The upper bound for the design variable. This is the maximum value that the design variable can take during the optimization process.
- `units`: The units for the design variable. This is used to convert the design variable to the appropriate units for the optimization algorithm.

This is not an exhaustive list of the design variable specifications.

```{note}
Any keyword arguments that are accepted by the OpenMDAO `add_design_var` method can be used in the design variable specification.
See [this doc page](https://openmdao.org/newdocs/versions/latest/features/core_features/adding_desvars_cons_objs/adding_design_variables.html) for more details and an exhaustive list of options.
```

## Constraints

Much like design variables, constraints are defined in the driver config file under the `constraints` section on a per-technology basis.
Any output from a component in H2I that is exposed to OpenMDAO can be a constraint.
H2I arbitrarily handles nonlinear and linear constraints.

In this example, we have a single constraint, `total_hydrogen_produced`, which is the total amount of hydrogen produced by the electrolyzer in kilograms per year.
In short, this constraint is saying that the total amount of hydrogen produced by the electrolyzer must be greater than or equal to 60,500,000 kg/year.

We define the following properties for this constraint:
- `flag`: A boolean flag that indicates whether the constraint is enabled or not. If set to `True`, the constraint will be included in the optimization problem.
- `lower`: The lower bound for the constraint. This is the minimum value that the constraint can take during the optimization process.
- `units`: The units for the constraint. This is used to convert the constraint to the appropriate units for the optimization algorithm.

This is not an exhaustive list of the constraint specifications.

```{note}
Any keyword arguments that are accepted by the OpenMDAO `add_constraint` method can be used in the constraint specification.
See [this doc page](https://openmdao.org/newdocs/versions/latest/features/core_features/adding_desvars_cons_objs/adding_constraint.html) for more details and an exhaustive list of options.
```

## Objective function

Lastly, as you might expect, the `objective` section of the driver config file defines the objective function for the optimization problem.
The objective function is the quantity that we are trying to minimize during the optimization process.
In this example, we have a single objective function, `finance_subgroup_default.LCOH`, which is the levelized cost of hydrogen (LCOH) produced by the electrolyzer.
The objective function is defined as a string that specifies the name of the objective function in the analysis.

The `promoted_name` of the objective function is used to identify the objective function in the analysis.
After each run of an H2I case, the outputs are printed to the screen like this:

```
27 Explicit Output(s) in 'model'

varname                               val                  units      prom_name
------------------------------------  -------------------  ---------  -------------------------------------------------------------
<...cut for brevity...>
    ProFastComp_0
      LCOE                            [0.09009908]         USD/(kW*h)   finance_subgroup_default.LCOE
    ProFastComp_1
      LCOH                            [4.63528661]         USD/kg     finance_subgroup_default.LCOH
```

This is the name that you will use to reference the objective function in the driver config file and it is useful to refer to this output when you are setting up your optimization problem.

```{note}
The default behavior of the optimization driver is to minimize the objective function.
If you want to maximize the objective function, you can set the `ref` keyword argument in the driver config file to -1.
```
