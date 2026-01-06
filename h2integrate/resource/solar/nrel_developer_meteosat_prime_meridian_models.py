from pathlib import Path

from attrs import field, define

from h2integrate.core.validators import contains, range_val
from h2integrate.resource.resource_base import ResourceBaseAPIConfig
from h2integrate.resource.solar.nrel_developer_api_base import NRELDeveloperAPISolarResourceBase


@define(kw_only=True)
class MeteosatPrimeMeridianAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `Meteosat Prime Meridian PSM v4 <https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-download/>`_.
    This dataset covers regions covered by the Meteosat Prime Meridian satellite (Africa and Europe)
    at a spatial resolution of 4 km.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 2005 and 2022 (inclusive).
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "nsrdb_msg_v4".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "solar".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` are 15, 30, and 60 minutes.

    """

    resource_year: int = field(converter=int, validator=range_val(2005, 2022))
    dataset_desc: str = "nsrdb_msg_v4"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [15, 30, 60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class MeteosatPrimeMeridianSolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = (
            "https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-msg-v1-0-0-download.csv?"
        )
        # create the resource config
        self.config = MeteosatPrimeMeridianAPIConfig.from_dict(resource_specs)
        super().setup()


@define(kw_only=True)
class MeteosatPrimeMeridianTMYAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `Meteosat Prime Meridian TMY: PSM v4 <https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-tmy-download/>`_,
    `Meteosat Prime Meridian TDY: PSM v4 <https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-tdy-download/>`_,
    and `Meteosat Prime Meridian TGY: PSM v4 <https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-msg-v1-0-0-tgy-download/>`_,
    This dataset covers regions within North and South America at a spatial resolution of 4 km.

    Args:
        resource_year (str): Year to use for resource data. Can be any of the following:
            tmy-2014, tdy-2014, tgy-2014, tmy-2022, tdy-2022, or tgy-2022
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "goes_aggregated_v2".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "solar".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` is minutes.

    """

    resource_year: str = field(
        converter=str.lower,
        validator=contains(
            [
                "tmy-2014",
                "tdy-2014",
                "tgy-2014",
                "tmy-2022",
                "tdy-2022",
                "tgy-2022",
            ]
        ),
    )
    dataset_desc: str = "nsrdb_msg_tmy_v4"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)

    def __attrs_post_init__(self):
        if "tmy" in self.resource_year:
            self.dataset_desc = "nsrdb_msg_tmy_v4"
        if "tdy" in self.resource_year:
            self.dataset_desc = "nsrdb_msg_tdy_v4"
        if "tgy" in self.resource_year:
            self.dataset_desc = "nsrdb_msg_tgy_v4"


class MeteosatPrimeMeridianTMYSolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        # create the resource config
        self.config = MeteosatPrimeMeridianTMYAPIConfig.from_dict(resource_specs)

        self.base_url = f"https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-msg-v1-0-0-{self.config.resource_year.split('-')[0]}-download.csv?"

        super().setup()
