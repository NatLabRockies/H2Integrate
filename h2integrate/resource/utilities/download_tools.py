import json
import time
from pathlib import Path

import requests


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
