# Wind Plant - Ard

The intent of [Ard](https://github.com/NLRWindSystems/Ard) is to be a modular, full-stack multi-disciplinary optimization tool for wind farms. By incorporating Ard in H2Integrate, we are able to draw on many wind technology models developed at the National Laboratory of the Rockies (NLR) and other institutions without managing them or their connections in Ard. Models connected in Ard include many parts of [WISDEM](https://github.com/NLRWindSystems/WISDEM), [FLORIS](https://github.com/NatLabRockies/floris), and [OptiWindNet](https://github.com/DTUWindEnergy/OptiWindNet). Ard also provides constraint functions and wind farm layout generation capabilities among other things. Because Ard has been developed in a modular way, you may also extend Ard fairly easily to include other wind models of interest.

Ard is included in H2Integrate as an [OpenMDAO sub-model](https://openmdao.org/newdocs/versions/latest/features/building_blocks/components/submodel_comp.html), which means that Ard is treated as a distinct and separate OpenMDAO problem within the larger H2I OpenMDAO problem. In this way, the user can run an independent wind farm optimization within Ard, or allow H2Integrate to manage the wind farm design variables directly. One drawback of including Ard as a sub-model is that N2 diagrams made from the H2Integrate problems will show Ard only as a single black-box model, rather than showing all the subsystems within Ard. If you wish to view an N2 diagram of Ard, you will need to use the Ard problem instead. The Ard subproblem can be created using Ard as a standalone package (see the [Ard documentation](https://nlrwindsystems.github.io/Ard/intro.html)) or by accessing the Ard subproblem in the H2Integrate problem by running a command such as `om.n2(h2i_model.prob.model.plant.wind.wind.ard_sub_prob._subprob)`, where the exact path of the `ard_sub_prob` may differ in your model depending on your config and names.

## Required input files and information unique to using Ard in H2Integrate

### WindIO input file
The WindIO input file is a yaml containing most of the information necessary to set up a wind farm simulation in Ard, including the wind turbine specifications, wind resource data, initial wind farm layout, substation positions, farm boundaries, etc. Other required information is passed to Ard in the H2Integrate `tech_config.yaml`. The WindIO input file may in turn be broken out into other yamls to be imported into the primary WindIO file as done in example `xx_wind_ard`. Detailed information for creating a WindIO input file can be found in the [WindIO documentation](https://github.com/IEAWindSystems/windIO). The WindIO filepath is provided to Ard via the `tech_config.yaml` as discussed below.

### Ard system and data path
When using Ard as a standalone model, an `ard_system.yaml` file is used and a data path is provided directly. When using Ard in H2Integrate, the data path and the `ard_system.yaml` contents are passed to Ard via the H2Integrate `tech_config.yaml`. The `ard_data_path` points to the directory containing all input files for Ard relative to working directory. The primary components of the `ard_system` inputs are: (1) the `system` which is a key-word relating to a pre-defined set of sub-models in Ard that the user needs to simulate their wind farm; (2) the `modeling_options` which contains the WindIO plant definition, or file path, along with initial variable values, cost information, and sub-model options; and (3) the `analysis_options` where Ard-specific analyses can be defined (like an optimization or a design of experiments).

An example of a technology config is shown below:
```yaml
technologies:
    wind:
        model_inputs:
            performance_model:
                model: "ard_wind_plant_combined"
            cost_model:
                model: "ard_wind_plant_combined"
            cost_parameters:
                cost_year: 2024
            performance_parameters:
                ard_data_path: "./"
                ard_system:
                    system: "onshore_batch"
                    modeling_options:
                        windIO_plant: !include ../ard_inputs/windio.yaml
                        layout:
                            N_turbines: 9
                            N_substations: 1
                            spacing_primary: 7.0
                            spacing_secondary: 7.0
                            angle_orientation: 0.0
                            angle_skew: 0.0
                        aero:
                            return_turbine_output: False
                        floris:
                            peak_shaving_fraction: 0.2
                            peak_shaving_TI_threshold: 0.0
                        collection:
                            max_turbines_per_string: 8
                            solver_name: "highs"
                            solver_options:
                            time_limit: 60
                            mip_gap: 0.02
                            model_options:
                            topology: "branched"  # "radial", "branched"
                            feeder_route: "segmented"
                            feeder_limit: "unlimited"
                        offshore: false
                        floating: false
                        costs:
                            rated_power: 5000000.0  # W
                            num_blades: 3
                            rated_thrust_N: 823484.4216152605 # from NREL 5MW definition
                            gust_velocity_m_per_s: 70.0 # from https://github.com/WISDEM/WISDEM/blob/master/examples/02_reference_turbines/nrel5mw.yaml
                            blade_surface_area: 69.7974979
                            tower_mass: 620.4407337521
                            nacelle_mass: 101.98582836439
                            hub_mass: 8.38407517646
                            blade_mass: 14.56341339641
                            foundation_height: 0.0
                            commissioning_cost_kW: 44.0 # from https://github.com/WISDEM/WISDEM/blob/master/examples/02_reference_turbines/nrel5mw.yaml
                            decommissioning_cost_kW: 58.0 # from https://github.com/WISDEM/WISDEM/blob/master/examples/02_reference_turbines/nrel5mw.yaml
                            trench_len_to_substation_km: 50.0
                            distance_to_interconnect_mi: 4.97096954
                            interconnect_voltage_kV: 130.0 # from https://github.com/WISDEM/WISDEM/blob/master/examples/02_reference_turbines/nrel5mw.yaml
                            tcc_per_kW: 1300.00  # (USD/kW)
                            opex_per_kW: 44.00  # (USD/kWh)
                    analysis_options:
```

## Some Key Capabilities of Ard
- Highly modular to include alternate/new models and capabilities
    - Built using OpenMDAO
- Wind farm layout optimization
    - Turbine locations
        - Ordered grid layouts
        - Continuous locations layouts
    - Boundaries
        - Single boundary
        - Multiple discrete boundary regions
        - Arbitrary polygonal boundaries shapes
- Collection cable array optimization
    - OptiWindNet
        - Radial configurations
        - Branched configurations
- Aerodynamics
    - FLORIS
- Cost and finance
    - WISDEM
        - LandBOSSE
        - ORBIT
        - FinanceSE

## Wind Resource
The wind resource capabilities of H2Integrate are not yet connected with Ard, so the user must provide a wind resource file directly to the Ard model inputs. Ard is built on WindIO, so the wind resource must be specified in a way compatible with WindIO. The basic information required is a time stamp, wind speed (m/s), wind direction (deg.), and turbulence intensity (unitless), but other information may be included. See the [WindIO documentation](https://ieawindsystems.github.io/windIO/2.0.1/source/plant_schema.html) for details.

## Examples
For an example of using Ard in an H2Integrate model, see `examples/xx_wind_ard`. Note that Ard uses a combination of input files, including a [wind IO](https://github.com/IEAWindSystems/windIO) file.
