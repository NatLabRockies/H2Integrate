(run_of_river_hydro)=
# Run-of-river hydropower model

{py:class}`~h2integrate.converters.water_power.hydro_plant_run_of_river.RunOfRiverHydroPerformanceModel`,
configured by
{py:class}`~h2integrate.converters.water_power.hydro_plant_run_of_river.RunOfRiverHydroPerformanceConfig`,
simulates electricity generation from river flow. The
{py:class}`~h2integrate.converters.water_power.hydro_plant_run_of_river.RunOfRiverHydroCostModel`
uses {py:class}`~h2integrate.converters.water_power.hydro_plant_run_of_river.RunOfRiverHydroCostConfig`
to calculate capital and fixed operating costs.
The run-of-river model is representative of a canal and/or penstock that produces energy by using the natural decline of the river bed elevation.
The model uses a simple formula to calculate the power generated based on the flow rate and the height difference between the water source and the turbine.
This doc page walks you through how to obtain resource information and how to use the model.

The {py:class}`~h2integrate.resource.river.RiverResource` component and its
{py:class}`~h2integrate.resource.river.RiverResourceConfig` read the discharge file. The resource
outputs 8,760 hourly `discharge` values in `ft**3/s`. Its latitude and longitude inputs do not
select the file. The performance model takes `discharge` in `m**3/s`, clips electricity production to the
configured capacity, and reports `electricity_out`, rated and annual production, and capacity
factor. Both hydro models support one-hour time steps. With system-level control, electricity
output is curtailed after production summaries are calculated, so those summaries reflect
uncurtailed production.

## Configuration

The model and resource configurations are generated from their API documentation:

```{eval-rst}
.. autoclass:: h2integrate.converters.water_power.hydro_plant_run_of_river.RunOfRiverHydroPerformanceConfig
   :no-members:
   :no-index:

.. autoclass:: h2integrate.converters.water_power.hydro_plant_run_of_river.RunOfRiverHydroCostConfig
   :no-members:
   :no-index:

.. autoclass:: h2integrate.resource.river.RiverResourceConfig
   :no-members:
   :no-index:
```

```{note}
This process is quite manual and not as automated as obtaining other resource information.
This is because river information is available at discrete station locations along waterways and each station has different sensor information reported.
```

```{note}
The legacy USGS NWIS Web Interface used in the screenshots is scheduled for decommissioning in late 2026; see the [USGS modernization timeline](https://waterdata.usgs.gov/blog/nwisweb-decommission-campaign3/). The current `RiverResource` importer expects the tab-delimited export from that interface, so check the USGS updates before following these steps.
```

## Obtaining river resource information

The only river resource information needed is the volumetric discharge of the river.
This can obtained from various sources, but we recommend using the [USGS National Water Information System](https://waterdata.usgs.gov/nwis/rt) for US rivers.
We'll guide you through the process of obtaining the flow rate from the USGS website.

1. Go to the [USGS National Water Information System](https://waterdata.usgs.gov/nwis/uv) website, shown below:

| ![USGS National Water Information System](images/usgs_river_info.png) |
|-|

   Determine the site number of the river you want to obtain information for.
   You can find the site number by searching for the river name or location on the USGS website.
   Here, we'll select the `State/Territory` option and click `Submit`.

2. On the next screen, you can select the area of interest.
   For this example, we'll select Kansas then scroll to the bottom of the page and select `Show sites on a map` then `Submit`.
   This will show you a map of the sites in Kansas.

| ![USGS State/Territory](images/river_timeseries.png) |
|-|

| ![Selecting Kansas](images/submit_query.png) |
|-|

3. This brings us to a map of the sites in Kansas.
   You can zoom in and out to find the site you're interested in.
   For this example, we'll select the `KANSAS R AT DESOTO, KS` site as shown in the image below.
   This gives us the site number `06892350` which we will use to download the relevant river data.

| ![Selecting site on map](images/river_map.jpg) |
|-|

4. Next, return to the [USGS National Water Information System homepage](https://waterdata.usgs.gov/nwis/uv) and select the `Site Number` option then click `Submit`.
   On the next screen, enter the site number `06892350` as shown below then scroll to the bottom of the page.

| ![Selecting site number](images/site_number_input.png) |
|-|

```{note}
Not all sites include discharge data.
Please check the site information to ensure that the site you selected has discharge data (in cubic feet per second) available.
```

5. Now you can select the date range that you're interested in.
   The current `RiverResource` importer requires exactly 8,760 hourly values for one year of data. Select the start and end dates accordingly; multi-year river files are not supported by this importer.
   In this example, we select the start date as `2024-05-01` and the end date as `2025-04-30`.
   Then, select the `Tab-separated data` option and click `Submit`.
   This will download a file with the river data in tab-separated format.
   Rename this file to have a `.csv` extension for use in H2Integrate.

| ![Selecting date range](images/site_options.png) |
|-|

## Using the downloaded river data

Now that you have the river data, you can use it in H2Integrate.
Follow the `07_run_of_river_plant` example script and yaml files to see how to use the river data in H2Integrate.

You will need to specify the path to the downloaded river data file in the `plant_config` yaml and also specify the resource being used for the river technology model in the `tech_config` yaml.
Also within the `tech_config` yaml, you can set the performance and cost parameters for the hydroelectric plant.

For additional information regarding hydropower technology and performance see
[New Stream-reach Development: A Comprehensive Assessment of Hydropower Energy Potential in the United States](https://info.ornl.gov/sites/publications/Files/Pub46481.pdf) and
for relevant performance and cost assumptions see the [Annual Technology Baseline - Hydropower](https://atb.nlr.gov/electricity/2024/hydropower).
