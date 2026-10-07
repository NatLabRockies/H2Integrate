import numpy as np
import pytest
import openmdao.api as om

from h2integrate.resource.solar.nlr_developer_goes_api_models import (
    GOESTMYSolarAPI,
    GOESAggregatedSolarAPI,
)
from h2integrate.resource.solar.nlr_developer_himawari_api_models import Himawari7SolarAPI


# docs fencepost start: DO NOT REMOVE
# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,resource_year,tz,dt,n_timesteps,include_leap,resource_fname,yr_order,model",
    [
        # --- Multiple years ---
        (-27.3649,152.67935,2012,0,3600,17544,True,"",None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,17520,False,"",None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,26280,False,"",[2012,2013,2012],Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,26304,True,"",[2012,2013,2013],Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,17544,True,["-27.3649_152.67935_2012_himawari7_v3_60min_utc_tz.csv","-27.3649_152.67935_2013_himawari7_v3_60min_utc_tz.csv"],None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,17520,False,["-27.3649_152.67935_2012_himawari7_v3_60min_utc_tz.csv","-27.3649_152.67935_2013_himawari7_v3_60min_utc_tz.csv"],None,Himawari7SolarAPI),
        # --- TMY ---
        (47.5233,-92.5366,"tmy-2022",-1,3600,17520,False,"",None,GOESTMYSolarAPI),
        (47.5233,-92.5366,"tmy-2022",-1,3600,26280,False,"",["tmy-2022","tmy-2023","tmy-2022"],GOESTMYSolarAPI),
        (47.5233,-92.5366,"tmy-2022",-1,3600,17520,False,["47.5233_-92.5366_tmy-2022_goes_tmy_v4_60min_local_tz.csv","47.5233_-92.5366_tmy-2022_goes_tmy_v4_60min_local_tz.csv"],None,GOESTMYSolarAPI),
        # --- Partial years ---
        (-27.3649,152.67935,2012,0,3600,13164,True,"",None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,13140,False,"",None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,4380,False,"",None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,4404,True,"",None,Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,21900,False,"",[2013,2012,2013],Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,21948,True,"",[2012,2013,2012],Himawari7SolarAPI),
        (-27.3649,152.67935,2012,0,3600,4404,True,"-27.3649_152.67935_2012_himawari7_v3_60min_utc_tz.csv",None,Himawari7SolarAPI),

        ],
    ids=[
        # --- Multiple years ---
        "Himawari7:2years-with-leapday-start_year",
        "Himawari7:2years-without-leapday-start_year",
        "Himawari7:3years-without-leapday-year_order",
        "Himawari7:3years-with-leapday-year_order",
        "Himawari7:2years-with-leapday-filenames",
        "Himawari7:2years-without-leapday-filenames",
        # --- TMY ---
        "GOESTMY:2years-start_year",
        "GOESTMY:3years-year_order",
        "GOESTMY:2years-filenames",
        # --- Partial years ---
        "Himawari7:1.5years-with-leapday-start_year",
        "Himawari7:1.5years-without-leapday-start_year",
        "Himawari7:0.5years-without-leapday-start_year",
        "Himawari7:0.5years-with-leapday-start_year",
        "Himawari7:2.5years-without-leapday-year_order",
        "Himawari7:2.5years-with-leapday-year_order",
        "Himawari7:0.5years-with-leapday-start_year_with_filename",
        ]
)
# fmt: on
def test_solar_resource_nonannual(
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

    with subtests.test("have at least 5 timeseries keys"):
        assert len(ts_keys)>5
    with subtests.test(f"timeseries is {n_timesteps}"):
        assert all(len(solar_resource[k])==n_timesteps for k in ts_keys)


# docs fencepost start: DO NOT REMOVE
# fmt: off
@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,resource_year,tz,dt,n_timesteps,include_leap,resource_fname,yr_order,model",
    [
        (34.22,-102.75,2012,0,3600,17520,False,"",None,GOESAggregatedSolarAPI),
        (34.22,-102.75,2012,0,3600,17520,False,"",[2013, 2012],GOESAggregatedSolarAPI),
        (34.22,-102.75,2012,0,3600,17520,False,["34.22_-102.75_2012_goes_aggregated_v4_60min_utc_tz.csv","34.22_-102.75_2013_goes_aggregated_v4_60min_utc_tz.csv"],None,GOESAggregatedSolarAPI),
        (34.22,-102.75,2012,0,3600,17520,False,["34.22_-102.75_2012_goes_aggregated_v4_60min_utc_tz.csv","34.22_-102.75_2013_goes_aggregated_v4_60min_utc_tz.csv"],[2013,2012],GOESAggregatedSolarAPI),
    ],
    ids=[
        "GOESAggregated-2year-start_year",
        "GOESAggregated-2year-year_order",
        "GOESAggregated-2year-filenames-with-inferred",
        "GOESAggregated-2year-filenames-with-diff-yr-order",
        ]
)
# fmt: on
def test_solar_resource_multiyear_site_change(
    subtests,
    model,
    resource_config_multiyear,
    site_config_multiyear,
    plant_simulation_multiyear,
    yr_order,
    resource_fname
    ):
    # Test based on Example 22
    # 2012 and 2013 used for resource data
    # starting site: (34.22,-102.75)
    # changed site: (35.2018863,-101.945027)


    # site0 is at (34.22,-102.75)
    site0_expected_meta_data = {
        "id": 542970,
        "site_lat": 34.21,
        "site_lon": -102.74,
        "elevation": 1166.0,
    }
    site0_expected_avg_ghi = {
        "2012": 235.5974885844749,
        "2013": 237.34098173515983,
        "2012 and 2013": 236.46923515981734,
    }

    # site1 is at (35.2018863,-101.945027)
    site1_expected_meta_data = {
        "id": 564069,
        "site_lat": 35.21,
        "site_lon": -101.94,
        "elevation": 1133.0,
    }
    site1_expected_avg_ghi = {
        "2012": 230.99212328767123,
        "2013": 231.51027397260273,
        "2012 and 2013": 231.251198630137
    }


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

    if yr_order is not None and isinstance(resource_fname,list):
        # using filenames with yr_order as back-up
        # this is the test id "GOESAggregated-2year-filenames-with-diff-yr-order"
        # in this case, the year-order is different when the site changes
        expected_site0_yr_order = [2012, 2013] # this is from filenames
        expected_site1_yr_order = [2013, 2012] # this is from yr_order
    elif yr_order is not None and isinstance(resource_fname, str):
        # using yr_order without filenames.
        # this is for the test id "GOESAggregated-2year-year_order"
        expected_site0_yr_order = yr_order
        expected_site1_yr_order = yr_order
    elif yr_order is None and isinstance(resource_fname, list):
        # inferring years from resource files
        # this is for test id "GOESAggregated-2year-filenames-with-inferred"
        expected_site0_yr_order = [2012, 2013]
        expected_site1_yr_order = [2012, 2013]
    else:
        expected_site0_yr_order = [2012, 2013]
        expected_site1_yr_order = [2012, 2013]
        # this is for test id "GOESAggregated-2year-start_year"


    prob.model.add_subsystem("resource", comp)
    prob.setup()
    prob.run_model()
    data_site0 = prob.get_val("resource.solar_resource_data").copy()
    idx_2012 = np.argwhere(data_site0["year"]==2012).flatten()
    idx_2013 = np.argwhere(data_site0["year"]==2013).flatten()
    if idx_2012[0] < idx_2013[0]:
        # 2012 happens before 2013
        site0_yr_order = [2012, 2013]
    else:
        site0_yr_order = [2013, 2012]

    # check site0 results
    site0_meta = {k:v for k,v in data_site0.items() if k in site0_expected_meta_data}

    with subtests.test("starting site rersource year order"):
        assert expected_site0_yr_order == site0_yr_order

    with subtests.test("starting site id, lat, lon, elevation"):
        assert site0_expected_meta_data == site0_meta
    with subtests.test("starting site average GHI in 2012"):
        ghi_2012_avg0 = data_site0["ghi"][idx_2012].mean()
        assert pytest.approx(site0_expected_avg_ghi["2012"], rel=1e-6) == ghi_2012_avg0
    with subtests.test("starting site average GHI in 2013"):
        ghi_2013_avg0 = data_site0["ghi"][idx_2013].mean()
        assert pytest.approx(site0_expected_avg_ghi["2013"], rel=1e-6) == ghi_2013_avg0
    with subtests.test("starting site average GHI in 2012 and 2013"):
        ghi_avg0 = data_site0["ghi"].mean()
        assert pytest.approx(site0_expected_avg_ghi["2012 and 2013"], rel=1e-6) == ghi_avg0


    # Change the site
    prob.set_val("resource.latitude", 35.2018863, units="deg")
    prob.set_val("resource.longitude", -101.945027, units="deg")
    prob.run_model()

    data_site1 = prob.get_val("resource.solar_resource_data").copy()
    idx_2012 = np.argwhere(data_site1["year"]==2012).flatten()
    idx_2013 = np.argwhere(data_site1["year"]==2013).flatten()

    if idx_2012[0] < idx_2013[0]:
        # 2012 happens before 2013
        site1_yr_order = [2012, 2013]
    else:
        site1_yr_order = [2013, 2012]

    site1_meta = {k:v for k,v in data_site1.items() if k in site1_expected_meta_data}
    with subtests.test("changed site rersource year order"):
        assert expected_site1_yr_order == site1_yr_order


    with subtests.test("changed site id, lat, lon, elevation"):
        assert site1_expected_meta_data == site1_meta
    with subtests.test("changed site average GHI in 2012"):
        ghi_2012_avg1 = data_site1["ghi"][idx_2012].mean()
        assert pytest.approx(site1_expected_avg_ghi["2012"], rel=1e-6) == ghi_2012_avg1


    with subtests.test("changed site average GHI in 2013"):
        ghi_2013_avg1 = data_site1["ghi"][idx_2013].mean()
        assert pytest.approx(site1_expected_avg_ghi["2013"], rel=1e-6) == ghi_2013_avg1
    with subtests.test("changed site average GHI in 2012 and 2013"):
        ghi_avg1 = data_site1["ghi"].mean()
        assert pytest.approx(site1_expected_avg_ghi["2012 and 2013"], rel=1e-6) == ghi_avg1
