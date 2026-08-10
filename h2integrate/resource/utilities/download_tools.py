import json
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from timezonefinder import TimezoneFinder


def download_from_api(url, filename):
    """Download data from `url` and save it to `filename`.

    Args:
        url (str): The API endpoint to return data from.
        filename (str): The filename where data should be written.

    Returns:
        bool: True if data was downloaded file successfully, False if encountered error.

    """
    n_tries = 0
    success = False
    while n_tries < 5:
        try:
            r = requests.get(url)
            if r:
                localfile = Path(filename).open("w+")
                # Use r.content.decode() to avoid charset_normalizer issues
                txt = (
                    r.content.decode("utf-8", errors="replace")
                    .replace("(Â°C)", "(C)")
                    .replace("(Â°)", "(deg)")
                )
                localfile.write(txt)
                localfile.close()
                if Path(filename).is_file():
                    success = True
                    break
            elif r.status_code == 400 or r.status_code == 403:
                print(r.url)
                err = r.text
                text_json = json.loads(r.text)
                if "errors" in text_json.keys():
                    err = text_json["errors"]
                raise requests.exceptions.HTTPError(err)
            elif r.status_code == 404:
                print(filename)
                raise requests.exceptions.HTTPError
            elif r.status_code == 429:
                raise RuntimeError("Maximum API request rate exceeded!")
            else:
                n_tries += 1
        except requests.exceptions.Timeout:
            time.sleep(0.2)
            n_tries += 1

    return success


def make_time_index_openmeteo(data, timezone, lat, lon):
    """Make a pd.DatetimeIndex object from the 'time' column of the input data.
    This is intended to be used with resource data obtained from
    OpenMeteo resource models.

    Args:
        data (pd.DataFrame): resource data with a 'time' column in ISO format
        timezone (str): name of timezone for the site. Only checked to see
            if timezone is 'UTC' or 'GMT'
        lat (float): site latitude
        lon (float): site longitude

    Returns:
        pd.DatetimeIndex: time index of OpenMeteo data
    """
    t0 = data["time"].iloc[0]
    t1 = data["time"].iloc[1]

    dt_t0 = datetime.fromisoformat(t0)
    dt_t1 = datetime.fromisoformat(t1)

    time_step_seconds = (dt_t1 - dt_t0).seconds

    # NOTE: unsure whether to adjust to middle of hour before
    # dt_t0 = dt_t0 - timedelta(seconds=time_step_seconds/2)

    freq = pd.to_timedelta(time_step_seconds, unit="s")
    if dt_t0.tzinfo is None:
        # missing timezone info
        if "T" in t0:
            # Web download, formatted as `YYYY-MM-DDTHH:mm` (ex: 2014-12-31T23:00)
            # downloaded in timezone specified but timestamps don't have timezone info
            return pd.DatetimeIndex(data["time"])

        # Old download method that had bugs
        # in UTC, times are in UTC (OK)
        if timezone != "GMT" and timezone != "UTC":
            # in local time, times were in UTC
            # and need to be converter to local timezone
            tf = TimezoneFinder()
            local_timezone = tf.timezone_at(lat=lat, lng=lon)
            # in local time, times are also in UTC
            dt_t0 = dt_t0.replace(tzinfo=ZoneInfo("UTC"))
            # convert those times to local time
            dt_t0 = dt_t0.astimezone(ZoneInfo(local_timezone))

    # Either the time column was already timezone aware or
    # has been adjusted to the proper timezone
    return pd.date_range(start=dt_t0, periods=len(data), freq=freq)
