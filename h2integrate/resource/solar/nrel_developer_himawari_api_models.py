from pathlib import Path

from attrs import field, define

from h2integrate.core.validators import contains, range_val
from h2integrate.resource.resource_base import ResourceBaseAPIConfig
from h2integrate.resource.solar.nrel_developer_api_base import NRELDeveloperAPISolarResourceBase


@define(kw_only=True)
class Himawari7SolarAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `Himawari 2011-15: PSM v3 <https://developer.nrel.gov/docs/solar/nsrdb/himawari7-download/>`_.
    This dataset covers regions covered by the Himawari-7 satellite (Asia, Australia & Pacific)
    at a spatial resolution of 4 km.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 2011 and 2015 (inclusive).
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "himawari7_v3".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "solar".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` are 30 and 60 minutes.

    """

    resource_year: int = field(converter=int, validator=range_val(2011, 2015))
    dataset_desc: str = "himawari7_v3"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [30, 60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class Himawari7SolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = "https://developer.nrel.gov/api/nsrdb/v2/solar/himawari7-download.csv?"
        # create the resource config
        self.config = Himawari7SolarAPIConfig.from_dict(resource_specs)
        super().setup()


@define(kw_only=True)
class Himawari8SolarAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `Himawari 2016-2020: PSM v3 <https://developer.nrel.gov/docs/solar/nsrdb/himawari-download/>`_.
    This dataset covers regions covered by the Himawari-8 satellite (Asia, Australia & Pacific)
    at a spatial resolution of 2 km.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 2016 and 2020 (inclusive).
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "himawari8_v3".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "solar".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` are 10, 30, and 60 minutes.

    """

    resource_year: int = field(converter=int, validator=range_val(2016, 2020))
    dataset_desc: str = "himawari8_v3"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [10, 30, 60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class Himawari8SolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = "https://developer.nrel.gov/api/nsrdb/v2/solar/himawari-download.csv?"
        # create the resource config
        self.config = Himawari8SolarAPIConfig.from_dict(resource_specs)
        super().setup()


@define(kw_only=True)
class HimawariTMYAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download solar resource data from
    `Himawari TMY: PSM v3 <https://developer.nrel.gov/docs/solar/nsrdb/himawari-tmy-download/>`_.
    This dataset covers regions within Asia, Australia & Pacific at a spatial resolution of 4 km.

    Args:
        resource_year (str): Year to use for resource data. Can be any of the following:
            tmy-2020, tdy-2020, or tgy-2020
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "himawari_tmy_v3".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "solar".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` is minutes.

    """

    resource_year: str = field(
        converter=str.lower,
        validator=contains(
            [
                "tmy-2020",
                "tdy-2020",
                "tgy-2020",
            ]
        ),
    )
    dataset_desc: str = "himawari_tmy_v4"
    resource_type: str = "solar"
    valid_intervals: list[int] = field(factory=lambda: [60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)

    def __attrs_post_init__(self):
        if "tmy" in self.resource_year:
            self.dataset_desc = "himawari_tmy_v3"
        if "tdy" in self.resource_year:
            self.dataset_desc = "himawari_tdy_v3"
        if "tgy" in self.resource_year:
            self.dataset_desc = "himawari_tgy_v3"


class HimawariTMYSolarAPI(NRELDeveloperAPISolarResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = "https://developer.nrel.gov/api/nsrdb/v2/solar/himawari-tmy-download.csv?"
        # create the resource config
        self.config = HimawariTMYAPIConfig.from_dict(resource_specs)
        super().setup()
