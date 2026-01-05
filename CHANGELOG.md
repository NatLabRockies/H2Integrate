# Changelog
## 0.5.x [TBD]
- Updates models for NumPy version 2.4.0
- Update test values for WOMBAT update to 0.13.0
- Added standlone iron DRI and steel EAF performance and cost models
- Added capability to have transport models that require user input parameters
- Add geologic hydrogen surface processing converter

## 0.5.1 [December 18, 2025]

- Fixed tagged version number for release

## 0.5.0 [December 18, 2025]

### New Features and Technology Models

- Added PySAM Windpower performance model to simulate wind [PR 306](https://github.com/NREL/H2Integrate/pull/306)
- Added `simple_grid_layout.py` for wind plant layout modeling, can model square or rectangular layouts [PR 306](https://github.com/NREL/H2Integrate/pull/306)
- Added ability to visualize the wind plant layout for PySAM Windpower model using `post_process(show_plots=True)` [PR 306](https://github.com/NREL/H2Integrate/pull/306)
- Added Wind Annual Technology Baseline cost model `atb_wind_cost.py` [PR 306](https://github.com/NREL/H2Integrate/pull/306)
- Added resource models to make solar resource API calls to the NREL Developer GOES dataset [PR 279](https://github.com/NREL/H2Integrate/pull/279)
- Added solar resource models for Meteosat Prime Meridian and Himawari datasets available through NSRDB [PR 377](https://github.com/NREL/H2Integrate/pull/377)
- Added wind resource model for API calls to Open-Meteo archive [PR 332](https://github.com/NREL/H2Integrate/pull/332)
- Added PySAM battery model as a storage technology performance model [PR 211](https://github.com/NREL/H2Integrate/pull/211)
- Added framework to run heuristic load following dispatch for storage technologies [PR 211](https://github.com/NREL/H2Integrate/pull/211)
- Added storage auto-sizing performance model based on storage sizing calculations that existed in the coupled hydrogen storage performance and cost model [PR 324](https://github.com/NREL/H2Integrate/pull/324)
- Added grid converter performance and cost model which can be used to buy, sell, or buy and sell electricity to/from the grid [PR 340](https://github.com/NREL/H2Integrate/pull/340)
- Add feature for natural gas plant converter to take electricity demand as an input and added system capacity as an input [PR 334](https://github.com/NREL/H2Integrate/pull/334)
- Added standalone iron mine performance and cost model [PR 364](https://github.com/NREL/H2Integrate/pull/364)
- Add open-loop load demand controllers: `DemandOpenLoopConverterController` and `FlexibleDemandOpenLoopConverterController` [PR 328](https://github.com/NREL/H2Integrate/pull/328)

### Improvements and Refactoring

- Updated inputs for the `ATBBatteryCostModel` and `DemandOpenLoopController` so storage capacity and charge rate can be design variables [PR 290](https://github.com/NREL/H2Integrate/pull/290)
- Split out cost models from coupled hydrogen storage performance and cost model [PR 324](https://github.com/NREL/H2Integrate/pull/324)
- Created `ProFastBase`, a base class for the `ProFastLCO` and `ProFastNPV` models [PR 310](https://github.com/NREL/H2Integrate/pull/310)
- Added `ProFastNPV`, a finance model using ProFAST to calculate NPV of the commodity [PR 310](https://github.com/NREL/H2Integrate/pull/310)
- Moved `compute()` from `ProFastBase` to `ProFastLCO` [PR 310](https://github.com/NREL/H2Integrate/pull/310)
- Added `NumpyFinancialNPV`, a finance model that uses NumPy Financial npv to calculate the npv from the cash flows [PR 310](https://github.com/NREL/H2Integrate/pull/310)
- Added capability for user-defined finance models in the H2Integrate framework [PR 247](https://github.com/NREL/H2Integrate/pull/247)
- Enabled dynamic plant component sizing modes through the resizeable model class `ResizeablePerformanceModelBaseClass` [PR 198](https://github.com/NREL/H2Integrate/pull/198)
- Move geologic hydrogen models into specific geoh2 subsurface converters [PR 367](https://github.com/NREL/H2Integrate/pull/367)
- Updated generic combiner to accept any number of inflow streams instead of just 2 [PR 406](https://github.com/NREL/H2Integrate/pull/406)
- Allow multiple instances of the same electricity producing technologies using prefix-based matching [PR 397](https://github.com/NREL/H2Integrate/pull/397)
- Allow multiple instances of custom models in the same hybrid system [PR 397](https://github.com/NREL/H2Integrate/pull/397)
- Removed a large portion of the old GreenHEART code that was no longer being used [PR 384](https://github.com/NREL/H2Integrate/pull/384)
- Moved high-level tests to the appropriate directory and removed defunct tests [PR 412](https://github.com/NREL/H2Integrate/pull/412)

### Configuration and Optimization

- Added `tools/run_cases.py` with tools to run different `tech_config` cases from a spreadsheet, with new docs page to describe: docs/user_guide/how_to_run_several_cases_in_sequence.md [PR 242](https://github.com/NREL/H2Integrate/pull/242)
- Updated setting up recorder in `PoseOptimization` [PR 291](https://github.com/NREL/H2Integrate/pull/291)
- Added `create_om_reports` option to driver config to enable/disable OpenMDAO reports (N2 diagrams, etc.) [PR 308](https://github.com/NREL/H2Integrate/pull/308)
- Added design of experiment functionality [PR 314](https://github.com/NREL/H2Integrate/pull/314)
- Added "csvgen" as generator type for design of experiments [PR 314](https://github.com/NREL/H2Integrate/pull/314)
- Added `load_yaml()` function and flexibility to input a config dictionary to H2IntegrateModel rather than a filepath [PR 313](https://github.com/NREL/H2Integrate/pull/313)
- Removed `boundaries` from the necessary keys in `plant_config` validation [PR 361](https://github.com/NREL/H2Integrate/pull/361)
- Added ability for latitude and longitude to be design variables in design sweep [PR 336](https://github.com/NREL/H2Integrate/pull/336)

### Documentation, Examples, and Miscellaneous

- Added an optimized offshore methanol production case to examples/03_methanol/co2_hydrogenation_doc [PR 137](https://github.com/NREL/H2Integrate/pull/137)
- Improved the readability of the postprocessing printout [PR 361](https://github.com/NREL/H2Integrate/pull/361)
- Improved readability of the postprocessing printout by simplifying numerical representation, especially for years [PR 378](https://github.com/NREL/H2Integrate/pull/378)
- Fixed stoichiometry mistake in ammonia synloop [PR 363](https://github.com/NREL/H2Integrate/pull/363)

## 0.4.0 [October 1, 2025]

This release introduces significant new technology models and framework capabilities for system design and optimization, alongside major refactoring and user experience improvements.

### New Features and Technology Models

- Added capability for user-defined technologies in the H2Integrate framework, allowing for custom models to be integrated into the system [PR 128](https://github.com/NREL/H2Integrate/pull/128).
- Added a check for if a custom model's name clashes with an existing model name in the H2Integrate framework, raising an error if it does [PR 128](https://github.com/NREL/H2Integrate/pull/128).
- Added geologic hydrogen (GeoH2) converter and examples [PR 135](https://github.com/NREL/H2Integrate/pull/135).
- Added methanol production base class [PR 137](https://github.com/NREL/H2Integrate/pull/137).
- Added steam methane reforming methanol production technology [PR 137](https://github.com/NREL/H2Integrate/pull/137).
- Added CO2 hydrogenation methanol production technology [PR 137](https://github.com/NREL/H2Integrate/pull/137).
- Added run of river hydro plant model, an example, and a documentation page [PR 145](https://github.com/NREL/H2Integrate/pull/145).
- Added marine carbon capture base class [PR 165](https://github.com/NREL/H2Integrate/pull/165).
- Added direct ocean capture technology [PR 165](https://github.com/NREL/H2Integrate/pull/165).
- Added ammonia synloop, partially addressing [Issue 169](https://github.com/NREL/H2Integrate/issues/169) [PR 177](https://github.com/NREL/H2Integrate/pull/177).
- Added simple air separation unit (ASU) converter to model nitrogen production [PR 179](https://github.com/NREL/H2Integrate/pull/179).
- Added rule-based storage system control capability (e.g., for battery, H2, CO2) [PR 195](https://github.com/NREL/H2Integrate/pull/195).
- Added ocean alkalinity enhancement technology model [PR 212](https://github.com/NREL/H2Integrate/pull/212).
- Added `natural_gas_performance` and `natural_gas_cost` models, allowing for natural gas power plant modeling [PR 221](https://github.com/NREL/H2Integrate/pull/221).
- Added wind resource model, API baseclasses, updated examples, and documentation [PR 245](https://github.com/NREL/H2Integrate/pull/245).
- Added generic storage model, useful for battery, hydrogen, CO2, or other resource storage [PR 248](https://github.com/NREL/H2Integrate/pull/248).


### Improvements and Refactoring

- Removed the `to_organize` directory [PR 138](https://github.com/NREL/H2Integrate/pull/138).
- Updated the naming scheme throughout the framework so resources produced always have `_out` and resources consumed always have `_in` in their names [PR 148](https://github.com/NREL/H2Integrate/pull/148).
- Added ability to export ProFAST object to yaml file in `ProFastComp` [PR 207](https://github.com/NREL/H2Integrate/pull/207).
- Refactored `ProFastComp` and put in a new file (`h2integrate/core/profast_financial.py`). Added flexibility to allow users to specify different financial models [PR 218](https://github.com/NREL/H2Integrate/pull/218).
- Revamped the feedstocks technology group to allow for more precise modeling of feedstock supply chains, including capacity constraints and feedstock amount consumed [PR 221](https://github.com/NREL/H2Integrate/pull/221).
- Made `pipe` and `cable` substance-agnostic rather than hard-coded for `hydrogen` and `electricity` [PR 241](https://github.com/NREL/H2Integrate/pull/241).
- Updated option to pass variables in technology interconnections to allow for different variable names from source to destination in the format `[source_tech, dest_tech, (source_tech_variable, dest_tech_variable)]` [PR 236](https://github.com/NREL/H2Integrate/pull/236).
- Split out the electrolyzer cost models `basic` and `singlitico` for clarity [PR 147](https://github.com/NREL/H2Integrate/pull/147).
- Refactored the ammonia production model to use the new H2Integrate framework natively and removed the prior performance and cost functions [PR 163](https://github.com/NREL/H2Integrate/pull/163).
- Added a new ammonia production model which has nitrogen, hydrogen, and electricity inputs and ammonia output, with performance and cost functions [PR 163](https://github.com/NREL/H2Integrate/pull/163).
- Added WOMBAT electrolyzer O&M model [PR 168](https://github.com/NREL/H2Integrate/pull/168).
- Changed electrolyzer capacity to be specified as `n_clusters` rather than `rating` in electrolyzer performance model config [PR 194](https://github.com/NREL/H2Integrate/pull/194).
- Changed electrolyzer capacity to be an input to the electrolyzer cost models rather than pulled from the cost model config [PR 194](https://github.com/NREL/H2Integrate/pull/194).
- Added cost model base class and removed `plant_config['finance_parameters']['discount_years']['tech']`. Cost year is now an optional input (`tech_config[tech]['model_inputs']['cost_parameters']['cost_year']`) and a discrete output [PR 199](https://github.com/NREL/H2Integrate/pull/199).
- Added two ATB-compatible solar-PV cost models [PR 193](https://github.com/NREL/H2Integrate/pull/193).
- Update PySAM solar performance model to allow for more user-configurability [PR 187](https://github.com/NREL/H2Integrate/pull/187).
- Added `"custom_electrolyzer_cost"` model, an electrolyzer cost model that allows for user-defined CapEx and OpEx values [PR 227](https://github.com/NREL/H2Integrate/pull/227).
- Added variable O&M to `CostModelBaseClass` and integrated into finance-related models [PR 235](https://github.com/NREL/H2Integrate/pull/235).
- Improved `h2integrate/transporters/power_combiner.py` and enabled usage of multiple electricity producing technologies [PR 232](https://github.com/NREL/H2Integrate/pull/232).


### Configuration and Optimization

- Updated finance parameter organization naming in `plant_config` [PR 218](https://github.com/NREL/H2Integrate/pull/218).
- Changed finance handling to use `finance_subgroups` and `finance_groups` defined in the `plant_config` rather than previous `financial_groups` in the `tech_config` and `technologies_to_include_in_metrics` in `plant_config` [PR 240](https://github.com/NREL/H2Integrate/pull/240).
- Allow users to specify the technologies to include in the metrics calculations in the plant configuration file [PR 240](https://github.com/NREL/H2Integrate/pull/240).
- Added option for user to provide ProFAST parameters in finance parameters [PR 240](https://github.com/NREL/H2Integrate/pull/240).
- Changed `plant_config` `atb_year` entry to `financial_analysis_start_year` [PR 190](https://github.com/NREL/H2Integrate/pull/190).
- Added `simulation` section under `plant_config['plant']` that has information such as number of timesteps in the simulation, time step interval in seconds, simulation start time, and time zone [PR 219](https://github.com/NREL/H2Integrate/pull/219).
- Moved `overwrite_fin_values` to HOPP [PR 164](https://github.com/NREL/H2Integrate/pull/164).
- Enable optimization with HOPP technology ratings using `recreate_hopp_config_for_optimization` [PR 164](https://github.com/NREL/H2Integrate/pull/164).
- Made caching in the HOPP wrapper optional [PR 164](https://github.com/NREL/H2Integrate/pull/164).
- Added more available constraints from the HOPP wrapper useful for design optimizations [PR 164](https://github.com/NREL/H2Integrate/pull/164).


### Documentation, Examples, and Miscellaneous

- Added an example of a user-defined technology in the `examples` directory, demonstrating an extremely simple paper mill model [PR 128](https://github.com/NREL/H2Integrate/pull/128).
- Added example for running with HOPP as the only technology in the H2Integrate system [PR 164](https://github.com/NREL/H2Integrate/pull/164).
- Added an optimization example with a wind plant and electrolyzer to showcase how to define design variables, constraints, and objective functions [PR 126](https://github.com/NREL/H2Integrate/pull/126).
- Expanded docs to include a new section on modifying config dicts after model instantiation [PR 151](https://github.com/NREL/H2Integrate/pull/151).
- Added `*_out/` to `.gitignore` to avoid clutter [PR 191](https://github.com/NREL/H2Integrate/pull/191).
- Bump min Python version and removed unnecessary packages from `pyproject.toml` [PR 150](https://github.com/NREL/H2Integrate/pull/150).
- Bugfix: only run `pyxdsm` when there are connections in the system [PR 201](https://github.com/NREL/H2Integrate/pull/201).


## 0.3.0 [May 2, 2025]

- Introduced a fully new underlying framework for H2Integrate which uses [OpenMDAO](https://openmdao.org/), allowing for more flexibility and extensibility in the future
- Expanded introductory documentation
- Added TOL/MCH hydrogen storage cost model

## 0.2.1 Unreleased, TBD

- Fixed iron data save issue [PR 122](https://github.com/NREL/H2Integrate/pull/122)
- Added optional inputs to electrolyzer model, including curve coefficients and water usage rate.
- Bug-fix in electrolyzer outputs (H2_Results) if some stacks are never turned on.

## 0.2 [7 April, 2025]

- Allow users to save the H2IntegrateOutput class as a yaml file and read that yaml to an instance of the output class
- Include new plotting capabilities: (1) hydrogen storage, production, and dispatch; (2) electricity and hydrogen dispatch
- Remove reference_plants from examples. Reference plants can now be found in the [ReferenceHybridSystemDesigns](https://github.com/NREL/ReferenceHybridSystemDesigns) repository.
- Use sentence capitalization for plot labels and legends
- Use "metric ton" instead of "tonne" or "metric tonne" in all internal naming and plots
- Fix bug in hydrogen dispatch plotting by storing time series of hydrogen demand by hour
- Update the PEM efficiency to 51.0 kWh/kg from 54.6 kWh/kg
- Bumped PySAM version to 6+ and HOPP to 3.2.0
- Removed defunct conda build and upload scripts
- Return full solution dictionary from ProFAST, allowing access to CRF and WACC
- Renamed code from GreenHEART to H2Integrate
- Added iron processing framework and capabilities [PR 90](https://github.com/NREL/H2Integrate/pull/90)
- Added Martin and Rosner iron ore models, performance and cost for each [PR 90](https://github.com/NREL/H2Integrate/pull/90)
- Added Rosner direct reduction iron (DRI) model, performance and cost [PR 90](https://github.com/NREL/H2Integrate/pull/90)
- Added Martin transport module for performance and cost of iron [PR 90](https://github.com/NREL/H2Integrate/pull/90)
- Added generalized Stinn cost model for electrolysis of arbitrary materials [PR 90](https://github.com/NREL/H2Integrate/pull/90)

## v0.1.4 [4 February, 2025]

- Adds `CoolProp` to `pyproject.toml`
- Changes units of `lcoe_real` in `HOPPComponent` from "MW*h" to "kW*h"
- Adds `pre-commit`, `ruff`, and `isort` checks, and CI workflow to ensure these steps aren't
  skipped.
- Updates steel cost year to, 2022
- Updates ammonia cost year to, 2022
- Requires HOPP 3.1.1 or higher
- Updates tests to be compatible with HOPP 3.1.1 with ProFAST integration
- Removes support for python 3.9
- Add steel feedstock transport costs (lime, carbon, and iron ore pellets)
- Allow individual debt rate, equity rate, and debt/equity ratio/split for each subsystem
- Add initial docs focused on new H2Integrate development
- New documentation CI pipeline to publish documentation at nrel.github.io/H2Integrate/ and test
  that the documentation site will build on each pull request.
- Placeholder documentation content has been removed from the site build

## v0.1.3 [1 November, 2024]

- Replaces the git ProFAST installation with a PyPI installation.
- Removed dependence on external electrolyzer repo
- Updated CI to use conda environments with reproducible environment artifacts
- Rename logger from "wisdem/weis" to "h2integrate"
- Remove unsupported optimization algorithms

## v0.1.2 [28 October, 2024]

- Minor updates to examples for NAWEA workshop.
- Adds `environment.yml` for easy environment creation and H2Integrate installation.

## v0.1.1 [22 October, 2024]

- Hotfix for examples

## v0.1 [16 October, 2024]

- Project has been separated from HOPP and moved into H2Integrate, removing all HOPP infrastructure.
