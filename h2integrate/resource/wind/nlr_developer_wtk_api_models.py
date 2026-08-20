from pathlib import Path

from attrs import field, define, validators

from h2integrate.resource.resource_base import ResourceBaseAPIConfig
from h2integrate.resource.wind.nlr_developer_wtk_api_base import NLRDeveloperAPIWindResourceBase


@define(kw_only=True)
class WTKNLRDeveloperAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download wind resource data from
    `Wind Toolkit Data V2 <https://developer.nlr.gov/docs/wind/wind-toolkit/wtk-download/>`_.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 2007 and 2014 (inclusive).
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "wtk_v2".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "wind".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` are 5, 15, 30, and 60 minutes.

    """

    resource_year: int = field(converter=int, validator=(validators.ge(2007), validators.le(2014)))
    dataset_desc: str = "wtk_v2"
    resource_type: str = "wind"
    valid_intervals: list[int] = field(factory=lambda: [5, 15, 30, 60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class WTKNLRDeveloperAPIWindResource(NLRDeveloperAPIWindResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = "https://developer.nlr.gov/api/wind-toolkit/v2/wind/wtk-download.csv?"

        # create the resource config
        self.config = WTKNLRDeveloperAPIConfig.from_dict(
            resource_specs,
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()


@define(kw_only=True)
class WTKHRRRMETAPIConfig(ResourceBaseAPIConfig):
    """Configuration class to download wind resource data from
    `HRRR MET Toolkit <https://developer.nlr.gov/docs/wind/wind-toolkit/wtk-hrrr-met-toolkit-v1-0-0-download/>`_.
    This dataset covers the Continental United States at a spatial resolution of 2 km.

    Args:
        resource_year (int): Year to use for resource data.
            Must been between 2015 and 2025 (inclusive).
        resource_data (dict | object, optional): Dictionary of user-input resource data.
            Defaults to an empty dictionary.
        resource_dir (str | Path, optional): Folder to save resource files to or
            load resource files from. Defaults to "".
        resource_filename (str, optional): Filename to save resource data to or load
            resource data from. Defaults to None.

    Attributes:
        dataset_desc (str): description of the dataset, used in file naming.
            For this dataset, the `dataset_desc` is "hrrr_met_toolkit".
        resource_type (str): type of resource data downloaded, used in folder naming.
            For this dataset, the `resource_type` is "wind".
        valid_intervals (list[int]): time interval(s) in minutes that resource data can be
            downloaded in. For this dataset, `valid_intervals` is 60 minutes.

    """

    resource_year: int = field(converter=int, validator=(validators.ge(2015), validators.le(2025)))
    dataset_desc: str = "hrrr_met_toolkit"
    resource_type: str = "wind"
    valid_intervals: list[int] = field(factory=lambda: [60])
    resource_data: dict | object = field(default={})
    resource_filename: Path | str = field(default="")
    resource_dir: Path | str | None = field(default=None)


class HRRRMETToolkitWindAPI(NLRDeveloperAPIWindResourceBase):
    def setup(self):
        resource_specs = self.helper_setup_method()

        self.base_url = "https://developer.nlr.gov/api/wind-toolkit/v2/wind/wtk-hrrr-met-toolkit-v1-0-0-download.csv?"

        # create the resource config
        self.config = WTKHRRRMETAPIConfig.from_dict(
            resource_specs,
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()
