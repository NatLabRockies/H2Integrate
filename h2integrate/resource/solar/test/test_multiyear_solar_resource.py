import numpy as np
import pytest
import openmdao.api as om

from h2integrate.resource.solar.nlr_developer_goes_api_models import GOESTMYSolarAPI
from h2integrate.resource.solar.nlr_developer_himawari_api_models import Himawari7SolarAPI


# docs fencepost start: DO NOT REMOVE
# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,resource_year,tz,dt,n_timesteps,include_leap,yr_setting,resource_fname,yr_order,model",
    [
        (-27.3649,152.67935,2012,0,3600,17544,True,"start_year","",None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,17520,False,"start_year","",None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,26280,False,"year_order","",[2012,2013,2012],Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,26304,True,"year_order","",[2012,2013,2013],Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,17544,True,"filenames",["-27.3649_152.67935_2012_himawari7_v3_60min_utc_tz.csv","-27.3649_152.67935_2013_himawari7_v3_60min_utc_tz.csv"],None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,17520,False,"filenames",["-27.3649_152.67935_2012_himawari7_v3_60min_utc_tz.csv","-27.3649_152.67935_2013_himawari7_v3_60min_utc_tz.csv"],None,Himawari7SolarAPI),
        # ---
        (47.5233,-92.5366,"tmy-2022",-1,3600,17520,False,"start_year","",None,GOESTMYSolarAPI),
        (47.5233,-92.5366,"tmy-2022",-1,3600,26280,False,"year_order","",["tmy-2022","tmy-2023","tmy-2022"],GOESTMYSolarAPI),
        (47.5233,-92.5366,"tmy-2022",-1,3600,17520,False,"filenames",["47.5233_-92.5366_tmy-2022_goes_tmy_v4_60min_local_tz.csv","47.5233_-92.5366_tmy-2022_goes_tmy_v4_60min_local_tz.csv"],None,GOESTMYSolarAPI),
        ],
    ids=[
        "Himawari7:2years-with-leapday-start_year",
        "Himawari7:2years-without-leapday-start_year",
        "Himawari7:3years-without-leapday-year_order",
        "Himawari7:3years-with-leapday-year_order",
        "Himawari7:2years-with-leapday-filenames",
        "Himawari7:2years-without-leapday-filenames",
        # ---
        "GOESTMY:2years-start_year",
        "GOESTMY:3years-year_order",
        "GOESTMY:2years-filenames",
        ]
)
# fmt: on
def test_solar_resource_multi_year(
    subtests,
    model,
    resource_config_multiyear,
    site_config_multiyear,
    plant_simulation_multiyear,
    n_timesteps,
    ):

    plant_config = {
        "plant": plant_simulation_multiyear,
        "site": site_config_multiyear
    }

    prob = om.Problem()
    comp = model(
        plant_config=plant_config,
        resource_config=resource_config_multiyear,
        driver_config={},
    )

    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()

    solar_resource = prob.model.get_val("resource.solar_resource_data")

    ts_keys = [k for k,v in solar_resource.items() if isinstance(v, list | np.ndarray)]

    with subtests.test(f"timeseries is {n_timesteps}"):
        assert all(len(solar_resource[k])==n_timesteps for k in ts_keys)
