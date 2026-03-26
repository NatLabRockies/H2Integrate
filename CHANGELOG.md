# Changelog

## Unreleased
- Update energy conversion ratio in H2 SMR model [PR 606](https://github.com/NatLabRockies/H2Integrate/pull/606)
- Update iron models and examples [PR 601](https://github.com/NatLabRockies/H2Integrate/pull/601)
  - Remove outdated iron files
  - Consolidate iron examples into a single main folder
  - Add documentation for Rosner iron DRI and steel EAF models
- Breaks out pyomo controller simulation code from base class to individual controllers. [PR 587](https://github.com/NatLabRockies/H2Integrate/pull/587)
- Add tests for non-one valued charge, discharge, and round-trip efficiencies for the open-loop demand controller [PR 610](https://github.com/NatLabRockies/H2Integrate/pull/610)
- Updated the `StorageAutoSizingModel` and `PassThroughOpenLoopController` so that `commodity_set_point` is used as the storage dispatch command [PR 608](https://github.com/NatLabRockies/H2Integrate/pull/608)
- Updated the `SimpleGenericStorage` and `DemandOpenLoopStorageController` so that `commodity_set_point` is used as the storage dispatch command [PR 612](https://github.com/NatLabRockies/H2Integrate/pull/612)
- Add PySAM marine models [PR 607](https://github.com/NatLabRockies/H2Integrate/pull/607)
  - Add tidal resource model
  - Add pysam tidal performance model
  - Add pysam marine hydrokinetic cost model
- Updated the `StoragePerformanceModel` and `PySAMBatteryPerformanceModel` to be compatible with the open-loop storage control strategies [PR 613](https://github.com/NatLabRockies/H2Integrate/pull/613)
  - Removed `SimpleGenericStorage` and replaced usage with `StoragePerformanceModel`
  - Renamed `PassThroughOpenLoopController` to `SimpleStorageOpenLoopController`
  - Bugfix in pyomo control rules so that units such as `kg/h` can be used
  - Bugfix in tests of pyomo control strategies with `StoragePerformanceModel` so that the pathname attribute is correct
  - Added `demand_profile` as an input to `StoragePerformanceModel` and `PySAMBatteryPerformanceModel`
  - Renamed `xx_charge_fraction` to `xx_soc_fraction`
- Bugfix in `StoragePerformanceModel` and `PySAMBatteryPerformanceModel` for setting control inputs to account for cases with multiple storage technologies with different control strategy types [PR 615](https://github.com/NatLabRockies/H2Integrate/pull/615)
- Bugfix input energy to OAE financial model [PR 617](https://github.com/NatLabRockies/H2Integrate/pull/617)
  - Remove `MarineCarbonCapture` base classes
- Added the notion of multivariable commodity streams, which allow users to connect multiple variables between technologies with a single connection specification. [PR 480](https://github.com/NatLabRockies/H2Integrate/pull/480)
- Added base class (`StorageOpenLoopControlBase`) and base configuration class (`StorageOpenLoopControlBaseConfig`) for open-loop storage control strategies and updated the existing open-loop storage control strategies to inherit these [PR 619](https://github.com/NatLabRockies/H2Integrate/pull/619)
- Added a generic cost model for converters [PR 622](https://github.com/NatLabRockies/H2Integrate/pull/622)
- Updated the `StorageAutoSizingModel` model to be compatible with Pyomo control strategies [PR 621](https://github.com/NatLabRockies/H2Integrate/pull/621)

## 0.7.1 [March 13, 2026]

### Updates

- PySAM battery now takes in charge rate and storage capacity as inputs [PR 557](https://github.com/NatLabRockies/H2Integrate/pull/557)
- Removed unnecessary `tech_name` designations for some control techs in yamls [PR 559](https://github.com/NatLabRockies/H2Integrate/pull/559)
- Added a generic storage model that is compatible with the Pyomo controllers [PR 571](https://github.com/NatLabRockies/H2Integrate/pull/571)
- Add hydrogen steam methane reforming (SMR) performance and cost converter [PR 594](https://github.com/NatLabRockies/H2Integrate/pull/594)
- Introduced a keyword arg to `post_process` to allow users to choose if results are printed to the console. [PR 597](https://github.com/NatLabRockies/H2Integrate/pull/597)
- Renamed `min_charge_percent`, `max_charge_percent`, and `init_charge_percent` to
  `min_charge_fraction`, `max_charge_fraction`, and `init_charge_fraction` across all
  configuration classes, YAML configs, tests, and examples. These values are fractions
  between 0 and 1, so the previous "percent" naming was misleading. [PR 581](https://github.com/NatLabRockies/H2Integrate/pull/581)
- Reorganized utilities, split them out to appropriate modules [PR 586](https://github.com/NatLabRockies/H2Integrate/pull/586)
- Updates the PR Changelog requirement to include complete descriptions of updates and a link to the
  associated PR. [PR 572](https://github.com/NatLabRockies/H2Integrate/pull/572)
- Added a test and docs for sql to csv. [PR 582](https://github.com/NatLabRockies/H2Integrate/pull/582)
- Switch to using NLR instead of NREL throughout, especially for API key usage for resource acquisition. [PR 583](https://github.com/NatLabRockies/H2Integrate/pull/583)

### Fixes

- Fixed docs/example drift in design of experiments case. [PR 584](https://github.com/NatLabRockies/H2Integrate/pull/584)
- Fixed a bug within the H2 storage cost models that used max rate instead of average for H2 flows [PR 588](https://github.com/NatLabRockies/H2Integrate/pull/588)
- Fixed a bug in the discrete variable instantiation within the iron processing stack that caused a failure with OpenMDAO v3.43 [PR 595](https://github.com/NatLabRockies/H2Integrate/pull/595)
- Fixed a bug in model setup where transporters were added to the system at the end of the system instead after their source [PR 591](https://github.com/NatLabRockies/H2Integrate/pull/591)
- Fixed a bug in example 1 (steel) where a cable was included between the combiner to steel, but steel uses an internal grid connection [PR 591](https://github.com/NatLabRockies/H2Integrate/pull/591)
- Fixed a bug in charge and discharge efficiency handling in `StoragePerformanceModel` [PR 600](https://github.com/NatLabRockies/H2Integrate/pull/600)

## 0.7 [March 3, 2026]

### New Features

- Simple nuclear plant performance and cost model [PR 538](https://github.com/NatLabRockies/H2Integrate/pull/538)
- Refactored iron electrowinning model with performance and cost models based on recent literature from Humbert and Stinn [PR 432](https://github.com/NatLabRockies/H2Integrate/pull/432)
- Load following optimization dispatch [PR 407](https://github.com/NatLabRockies/H2Integrate/pull/407)
- Linearized hydrogen fuel cell model [PR 525](https://github.com/NatLabRockies/H2Integrate/pull/525)
- Arps decline rate now incorporated into the natural geologic hydrogen model [PR 454](https://github.com/NatLabRockies/H2Integrate/pull/454)
- Simple dispatch calculations now included in `StorageAutoSizingModel` [PR 493](https://github.com/NatLabRockies/H2Integrate/pull/493)

### Updates

#### Modeling

- Removed all uses of `prob["<variable>"]` in favor of `prob.get_val("<variable>", units="<units>")` to
  ensure units are properly handled and to prepare for the possibility of multiple variables with the
  same name but different units in the future. [PR 539](https://github.com/NatLabRockies/H2Integrate/pull/539)
- Update finance models to use annual capacity factor and rated production rather than annual production. [PR 552](https://github.com/NatLabRockies/H2Integrate/pull/552)
- Update `NaturalGeoH2PerformanceModel` outputs yearly metrics. [PR 552](https://github.com/NatLabRockies/H2Integrate/pull/552)
- Add figures and more description about how technologies and systems are modeled and connected in H2INtegrate. [PR 554](https://github.com/NatLabRockies/H2Integrate/pull/554)
- Generalize electrolyzer replacement schedule logic within the framework. [PR 555](https://github.com/NatLabRockies/H2Integrate/pull/555)

#### Infrastructure

- Insert model names for technologies with control strategies to simplify Pyomo workflows. [PR 558](https://github.com/NatLabRockies/H2Integrate/pull/558)
- Refactored pyomo code by splitting apart classes into separate files and removing unused properties [PR 549](https://github.com/NatLabRockies/H2Integrate/pull/549)
- Use the PyPI listed mcm package in place of installing from GitHub. [PR 533](https://github.com/NatLabRockies/H2Integrate/pull/533)
- Adds a duplicate key checker to the YAML `Loader` that raises an error when a duplicate key is
  found, and points to the file and line number that caused the error. The YAML `Loader` modification
  maintains compliance with the existing JSON validation protocols. [PR 534](https://github.com/NatLabRockies/H2Integrate/pull/534)
- Test infrastructure updates: [PR 531](https://github.com/NatLabRockies/H2Integrate/pull/531)
  - Introduces enforced test marking for `unit`, `regression`, and `integration` tests so that
    all tests must be marked via `@pytest.mark.<test-type>`.
  - Partial testing suite refactor to parameterize many of the common fixtures and test routines.
  - `unittest` style tests are refactored to be `pytest` style tests for test consistency.
- Adds a pre-commit hook for `yamlfix` to auto-format YAML files and `yamlfix`'d all YAML files for consistent formatting [PR 551](https://github.com/NatLabRockies/H2Integrate/pull/551)

## 0.6 [February 10, 2026]

### New Features and Technology Models

- Added standalone iron DRI and steel EAF performance and cost models [PR 409](https://github.com/NatLabRockies/H2Integrate/pull/409)
- Add geologic hydrogen surface processing converter [PR 405](https://github.com/NatLabRockies/H2Integrate/pull/405)
- Added [Ard](https://github.com/NLRWindSystems/Ard) as an optional combined performance and cost model [PR 481](https://github.com/NatLabRockies/H2Integrate/pull/481)
- Added ability to plot multi-layer geospatial point heat map and simple straight line transport routes with GeoPandas and Contextily [PR 413](https://github.com/NatLabRockies/H2Integrate/pull/413)

### Improvements and Refactoring

- Added `PerformanceModelBaseClass` and standardized outputs of converter performance models [PR 463](https://github.com/NatLabRockies/H2Integrate/pull/463)
- Updates all models in `supported_models` to map between a string version of the class name and
  the class itself. As such, all examples and documentation have been updated to properly instruct
  users to the change in model configuration naming conventions. The naming convention is also
  enforced by a newly added test to ensure adherence. [PR 468](https://github.com/NatLabRockies/H2Integrate/pull/468)
- Adds `additional_cls_name` kwarg to `BaseConfig.from_dict()` to allow for configuration errors buried in parent or child classes to provide which model had the offending misconfiguration for simpler user debugging. [PR 479](https://github.com/NatLabRockies/H2Integrate/pull/479)
- Added capability to have transport models that require user input parameters [PR 408](https://github.com/NatLabRockies/H2Integrate/pull/408)
- Add baseclass for caching functionality [PR 422](https://github.com/NatLabRockies/H2Integrate/pull/422)
- Minor reorg for profast tools [PR 450](https://github.com/NatLabRockies/H2Integrate/pull/450)
- Added postprocessing function to save timeseries [PR 440](https://github.com/NatLabRockies/H2Integrate/pull/440)
- Removed hydrogen tank cost and performance models that were unused [PR 457](https://github.com/NatLabRockies/H2Integrate/pull/457)
- Allow design variables to be specified with None type units [PR 514](https://github.com/NatLabRockies/H2Integrate/pull/514)

### Documentation, Examples, and Miscellaneous

- Updates models for NumPy version 2.4.0 [PR 422](https://github.com/NatLabRockies/H2Integrate/pull/422)
- Update test values for WOMBAT update to 0.13.0 [PR 425](https://github.com/NatLabRockies/H2Integrate/pull/425)
- Converted the documentation Jupyter notebooks to markdown files to simplify output diffs [PR 464](https://github.com/NatLabRockies/H2Integrate/pull/464)
- Updated the contributing documentation to clarify what developers should expect for including
  executable content in the documentation. [PR 464](https://github.com/NatLabRockies/H2Integrate/pull/464)
- Converted the example notebooks to documentation examples, and maintain a basic working example
  in the examples folder [PR 464](https://github.com/NatLabRockies/H2Integrate/pull/464):
  - `examples/14_wind_hydrogen_dispatch/hydrogren_dispatch.ipynb` -> `docs/control/controller_demonstrations.md`
  - `examples/20_solar_electrolyzer_doe/run_csv_doe.ipynb` content added to `docs/user_guide/design_of_experiments_in_h2i.md`
  - `examples/25_sizing_modes/run_size_modes.ipynb` -> `docs/user_guide/run_size_modes.md`
- `.gitignore` is updated to be more inclusive of example output data.
- Documentation builds will now fail if a demonstration errors during execution that is not marked as an allowed error, ensuring previously silent errors get caught. [PR 464](https://github.com/NatLabRockies/H2Integrate/pull/464)
- `pyproject.toml` is tidied up after moving past Python 3.9 and early H2I limitations. [PR 471](https://github.com/NatLabRockies/H2Integrate/pull/471)
  - Cleans up unnecessary ignore rules in the ruff settings.
  - Removes duplicate dependency listings, and alphabetizes for legibility with NLR packages
    listed at the bottom.
  - Remove unused dependencies.
  - Fixes typos for skipped folders.
  - Fixes missing dependencies for `gis` modifier used in new iron mapping tests.
  - Remove `pytest-subtests` as it's incorporated into pytest as of v9, and is an archived project.

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
