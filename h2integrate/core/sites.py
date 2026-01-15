import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig
from h2integrate.core.validators import range_val


@define
class SiteBaseConfig(BaseConfig):
    latitude: float = field(default=0.0, validator=range_val(-90.0, 90.0))
    longitude: float = field(default=0.0, validator=range_val(-180.0, 180.0))


class SiteBaseComponent(om.IndepVarComp):
    def __init__(self, name=None, val=1.0, **kwargs):
        # initialize config here from site_config

        super().__init__(name, val, **kwargs)

        self.add_output("latitude", val=self.config.latitude, units="deg")
        self.add_output("longitude", val=self.config.latitude, units="deg")

        self.set_outputs()

    def set_outputs(self):
        raise NotImplementedError("This method should be implemented in a subclass.")


@define
class SiteLocationComponentConfig(SiteBaseConfig):
    """Configuration class for defining a site component with SiteLocationComponent.

    Attributes:
        latitude (float, optional): latitude in degrees North of the Equator.
            Must be between -90 and 90. Defaults to 0.0
        longitude (float, optional): longitude in degrees East of the Prime Meridian.
            Must be between -180 and 180. Defaults to 0.
        elevation (float, optional): elevation of the site in meters. Defaults to 0.0
    """

    elevation: float | int = field(default=0.0)


class SiteLocationComponent(SiteBaseComponent):
    def __init__(self, site_config: dict, name=None, val=1.0, **kwargs):
        self.config = SiteLocationComponentConfig.from_dict(site_config)
        super().__init__(name, val, **kwargs)

    def set_outputs(self):
        # latitude and longitude are set as outputs in ``SiteBaseComponent.__init__()``
        self.add_output("elevation", val=self.config.elevation, units="m")
