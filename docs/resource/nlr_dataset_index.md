(h5_dataset:overview)=
# NLR Dataset Resource Extraction Models

These resource models use the [REsource eXtraction tool (rex)](https://github.com/NatLabRockies/rex) to load resource data from NLR datasets. Internal users can access these datasets on the [NLR HPC](https://www.nlr.gov/hpc/). External users can access these datasets through AWS S3 on your local computer using an [NLR API Key](https://developer.nlr.gov/signup/) (additional set-up and packages may be required, please see the 'External Users' section for more information)

# Model Overview

## Wind Resource Models
- `WTKHRRRMETDatasetH5`: dataset extraction equivalent of the [`HRRRMETToolkitWindAPI` API resource model](#wind_resource:hrrr_met_data)


## Solar Resource Models
- `NSRDBDatasetH5`: dataset extraction equivalent of the [`GOESConusSolarAPI` API resource model](#solar_resource:goes_v4_api)


# External Users

External users should follow the install and set-up instructions [available here](https://natlabrockies.github.io/rex/misc/examples.nlr_data.html#data-location-external-users). Additional set-up information and examples are available [here](https://natlabrockies.github.io/rex/misc/examples.hsds.html). If running with a local HSDS server, please set `use_hsds` to True in the `resource_parameters`. Also note that the `hsds_enpoint` in the rex documentation should be set as `hs_endpoint = https://developer.nlr.gov/api/hsds`

The S3 files for NSRDB are located in the `nrel-pds-nsrdb` [bucket on OEDI](https://data.openei.org/s3_viewer?bucket=nrel-pds-nsrdb). The S3 files for WTK are located in the `nrel-pds-wtk` [bucket on OEDI](https://data.openei.org/s3_viewer?bucket=nrel-pds-wtk).

```{important}
The S3 files can also be accessed using [`fsspec`](https://natlabrockies.github.io/rex/misc/examples.fsspec.html), [`Xarray`](https://natlabrockies.github.io/rex/misc/examples.xarray.html) and [`Zarr`](https://natlabrockies.github.io/rex/misc/examples.zarr.html) (as documented in the rex documentation), but the resource models in H2I may not be compatible with those methods yet. If you are an external user and don't have a local HSDS server set-up, it is recommended to make a custom resource model that inherits the relevant NLR dataset model and over-writes the logic that specifies the filepath for that dataset. All other functionality in the NLR dataset models should work as-intended.
```





# References

[1] Bodini, N., Buster, G., & Pinchuk, P. (2026). *HRRR Meteorology, Energy, and Transmission (MET) Toolkit*. [Data set]. Open Energy Data Initiative (OEDI). National Laboratory of the Rockies (NLR). https://data.openei.org/submissions/8636

[2] Sengupta, M., Habte, A., Xie, Y., Lopez, A., & Buster, G. (2018). *National Solar Radiation Database (NSRDB)*. [Data set]. Open Energy Data Initiative (OEDI). National Renewable Energy Laboratory. https://doi.org/10.25984/1810289
