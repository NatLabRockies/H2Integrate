from pathlib import Path

from attrs import field, define

from h2integrate.core.validators import contains, range_val
from h2integrate.resource.resource_base import ResourceBaseAPIConfig
from h2integrate.resource.solar.nrel_developer_api_base import NRELDeveloperAPISolarResourceBase


@define(kw_only=True)
class GOESAggregatedAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `GOES Aggregated PSM v4 <https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-aggregated-v4-0-0-download/>`_.
    This dataset covers regions within North and South America at a spatial resolution of 4 km.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 1998 and 2024 (inclusive).
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
            downloaded in. For this dataset, `valid_intervals` are 30 and 60 minutes.

    """

    resource_year: int = field(converter=int, validator=range_val(1998, 2024))
    dataset_desc: str = "goes_aggregated_v4"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [30, 60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class GOESAggregatedSolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = "https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-GOES-aggregated-v4-0-0-download.csv?"
        # create the resource config
        self.config = GOESAggregatedAPIConfig.from_dict(resource_specs)
        super().setup()


@define(kw_only=True)
class GOESConusAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `GOES Conus PSM v4 <https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-conus-v4-0-0-download/>`_.
    This dataset covers regions within the continental United States at a spatial resolution of
    2 km.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 2018 and 2024 (inclusive).
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
            downloaded in. For this dataset, `valid_intervals` are 5, 15, 30 and 60 minutes.

    """

    resource_year: int = field(converter=int, validator=range_val(2018, 2024))
    dataset_desc: str = "goes_conus_v4"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [5, 15, 30, 60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class GOESConusSolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = (
            "https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-GOES-conus-v4-0-0-download.csv?"
        )
        # create the resource config
        self.config = GOESConusAPIConfig.from_dict(resource_specs)
        super().setup()


@define(kw_only=True)
class GOESFullDiscAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `GOES Full Disc PSM v4 <https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-full-disc-v4-0-0-download/>`_.
    This dataset covers regions within North and South America at a spatial resolution of 2 km.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 2018 and 2024 (inclusive).
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
            downloaded in. For this dataset, `valid_intervals` are 10, 30 and 60 minutes.

    """

    resource_year: int = field(converter=int, validator=range_val(2018, 2024))
    dataset_desc: str = "goes_fulldisc_v4"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [10, 30, 60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class GOESFullDiscSolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = "https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-GOES-full-disc-v4-0-0-download.csv?"
        # create the resource config
        self.config = GOESFullDiscAPIConfig.from_dict(resource_specs)
        super().setup()


@define(kw_only=True)
class GOESTMYAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `GOES Full Disc PSM v4 <https://developer.nrel.gov/docs/solar/nsrdb/nsrdb-GOES-tmy-v4-0-0-download/>`_.
    This dataset covers regions within North and South America at a spatial resolution of 4 km.

    Args:
        resource_year (str): Year to use for resource data. Can be any of the following:
            tmy-2022, tdy-2022, tgy-2022, tmy-2023, tdy-2023, tgy-2023, tmy-2024, tdy-2024,
            or tgy-2024.
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
                "tmy-2022",
                "tdy-2022",
                "tgy-2022",
                "tmy-2023",
                "tdy-2023",
                "tgy-2023",
                "tmy-2024",
                "tdy-2024",
                "tgy-2024",
            ]
        ),
    )
    dataset_desc: str = "goes_tmy_v4"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)

    def __attrs_post_init__(self):
        if "tmy" in self.resource_year:
            self.dataset_desc = "goes_tmy_v4"
        if "tdy" in self.resource_year:
            self.dataset_desc = "goes_tdy_v4"
        if "tgy" in self.resource_year:
            self.dataset_desc = "goes_tgy_v4"


class GOESTMYSolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = (
            "https://developer.nrel.gov/api/nsrdb/v2/solar/nsrdb-GOES-tmy-v4-0-0-download.csv?"
        )
        # create the resource config
        self.config = GOESTMYAPIConfig.from_dict(resource_specs)
        super().setup()
