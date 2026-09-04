from attrs import field, define, validators
from geopy import distance

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class LinearTransportCostConfig(CostModelBaseConfig):
    """Configuration class for LinearDistanceCostModel

    Attributes:
        capex_per_km (float): Capital cost in USD/km.
        fixed_opex_per_km (float): Annual operating cost in USD/km/year
    """

    capex_per_km: float = field(validator=validators.ge(0))
    fixed_opex_per_km: float = field(validator=validators.ge(0))


class LinearDistanceCostModel(CostModelBaseClass):
    """
    Combine any commodity or resource from multiple sources into one output without losses.

    This component is purposefully simple; a more realistic case might include
    losses or other considerations from system components.
    """

    _time_step_bounds = (1, 1e9)

    def setup(self):
        self.add_input("source_latitude", 0.0, shape=1, require_connection=True, units="deg")
        self.add_input("source_longitude", 0.0, shape=1, require_connection=True, units="deg")
        self.add_input("dest_latitude", 0.0, shape=1, require_connection=True, units="deg")
        self.add_input("dest_longitude", 0.0, shape=1, require_connection=True, units="deg")
        self.add_output("transport_distance", 0.0, shape=1, units="km")

        self.config = LinearTransportCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        self.add_input("unit_capex", self.config.capex_per_km, units="USD/km")
        self.add_input("unit_fixed_opex", self.config.fixed_opex_per_km, units="USD/km/year")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        source_location = (inputs["source_latitude"][0], inputs["source_longitude"][0])
        destination_location = (inputs["dest_latitude"][0], inputs["dest_longitude"][0])

        # Calculate the distance bewteen the source and destination locations
        transport_distance = distance.geodesic(
            source_location, destination_location, ellipsoid="WGS-84"
        ).km

        outputs["transport_distance"] = transport_distance

        outputs["CapEx"] = transport_distance * inputs["unit_capex"]
        outputs["OpEx"] = transport_distance * inputs["unit_fixed_opex"]
