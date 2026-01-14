# Geologic Hydrogen Models

Within H2Integrate the geologic hydrogen models are divided into subsurface and surface models.
The hydrogen well subsurface models account for the drilling and completion of any wells, and the working fluids injected to extract or produce hydrogen using this technology.
The hydrogen surface processing models account for the above-surface processing or refinement of the raw hydrogen to commercial grade.

## Hydrogen Well Subsurface Models

There are two performance models available to model the hydrogen well subsurface: one for natural geologic hydrogen and one for stimulated geologic hydrogen.

- [`"simple_natural_geoh2_performance"`](#simple-natural-geoh2-performance): A basic natural geologic hydrogen model for calculating the wellhead gas flow over the well lifetime (`plant_life`) and the specific hydrogen flow from the accumulated gas.

- [`"templeton_serpentinization_geoh2_performance"`](#templeton-serpentinization-geoh2-performance): A stimulated geologic hydrogen model that estimates the hydrogen production from artificially stimulating geologic formations through a process called serpentinization.

There is one cost model available to model the hydrogen well subsurface, which applies to both natural and stimulated geologic hydrogen.

- [`"mathur_modified_geoh2_cost"`](#mathur-modified-geoh2-cost): A subsurface cost model that calculates the capital and operating for subsurface well systems in geologic hydrogen production.

(simple-natural-geoh2-performance)=
### Simple Natural GeoH2 Performance

The modeling approach in this performance model is informed by:
- [Mathur et al. (Stanford)](https://doi.org/10.31223/X5599G)
- [Gelman et al. (USGS)](https://doi.org/10.3133/pp1900)
- [Tang et al. (Southwest Petroleum University)](https://doi.org/10.1016/j.petsci.2024.07.029)

(templeton-serpentinization-geoh2-performance)=
### Templeton Serpentinization GeoH2 Performance

The modeling approach in this performance model is informed by:
- [Mathur et al. (Stanford)](https://doi.org/10.31223/X5599G)
- [Templeton et al. (UC Boulder)](https://doi.org/10.3389/fgeoc.2024.1366268)

(mathur_modified_geoh2_cost)=
### Mathur Modified GeoH2 Cost

The modeling approach in this cost model is based on:
- [Mathur et al. (Stanford)](https://doi.org/10.31223/X5599G)
- [NETL Quality Guidelines](https://doi.org/10.2172/1567736)
- Drill cost curves are based on an adapted [GETEM model](https://sam.nrel.gov/geothermal.html)

## Hydrogen Surface Processing Models

There is one performance model and one cost model available to model the hydrogen surface processing, and only for natural geologic hydrogen. There are currently no surface processing models implemented for stimulated geologic hydrogen.

- [`"aspen_geoh2_performance"`](#aspen-geoh2-surface-performance): A series of empirical relations between wellhead flow/concentration and processing plant performance, based on the [ASPEN](https://www.aspentech.com/en/products/engineering/aspen-plus) process models.

- [`"aspen_geoh2_cost"`](#aspen-geoh2-surface-cost): A series of empirical relations between wellhead flow/concentration and processing plant cost, based on the [ASPEN](https://www.aspentech.com/en/products/engineering/aspen-plus) process models.

(aspen-geoh2-surface-performance)=
### Aspen GeoH2 Performance

The modeling approach in this performance model is based on:
- [Mathur et al. (Stanford)](https://doi.org/10.31223/X5599G)

(aspen-geoh2-surface-cost)=
### Aspen GeoH2 Cost

The modeling approach in this cost model is based on:
- [Mathur et al. (Stanford)](https://doi.org/10.31223/X5599G)
