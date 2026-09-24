from attrs import field, define, validators
from geopy import distance

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class LinearMassTransportCostConfig(CostModelBaseConfig):
    """Configuration class for LinearMassTransportCostModel

    Attributes:
        capex_per_mton_km (float): Capital cost in USD/t-km (metric tonne)
        fixed_opex_per_mton_km (float): Annual operating cost in USD/t-km/year
        commodity (str): Name of commodity being transported
        circuity_ratio (float, optional): Ratio of actual travel distance to straight-line distance.
        Defaults to 1.0.
    """

    capex_per_mton_km: float = field(validator=validators.ge(0))
    fixed_opex_per_mton_km: float = field(validator=validators.ge(0))
    commodity: str = field()
    circuity_ratio: float = field(validator=validators.ge(1), default=1.0)


class LinearMassTransportCostModel(CostModelBaseClass):
    """
    Calculate capital and annual operating costs for transporting a commodity by mass and distance.

    The model calculates the geodesic distance between source and destination coordinates,
    adjusts it by a circuity ratio, and multiplies it by annual commodity throughput and
    the configured cost rates.
    """

    _time_step_bounds = (1, 1e9)

    def setup(self):
        self.add_input("source_latitude", 0.0, shape=1, require_connection=True, units="deg")
        self.add_input("source_longitude", 0.0, shape=1, require_connection=True, units="deg")
        self.add_input("dest_latitude", 0.0, shape=1, require_connection=True, units="deg")
        self.add_input("dest_longitude", 0.0, shape=1, require_connection=True, units="deg")

        self.add_output("transport_distance", 0.0, shape=1, units="km")

        self.config = LinearMassTransportCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )

        super().setup()

        self.add_input("circuity_ratio", self.config.circuity_ratio, units="unitless")
        self.add_input(f"{self.config.commodity}_in", val=0.0, shape=self.n_timesteps, units="t/h")

        self.add_input("unit_capex", self.config.capex_per_mton_km, units="USD/(km*t)")
        self.add_input(
            "unit_fixed_opex", self.config.fixed_opex_per_mton_km, units="USD/(km*t)/year"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # get commodity transported per year
        commodity_transported = (
            inputs[f"{self.config.commodity}_in"].sum() * self.fraction_of_year_simulated
        )

        source_location = (inputs["source_latitude"][0], inputs["source_longitude"][0])
        destination_location = (inputs["dest_latitude"][0], inputs["dest_longitude"][0])

        # Calculate the distance between the source and destination locations
        transport_distance = distance.geodesic(
            source_location, destination_location, ellipsoid="WGS-84"
        ).km

        outputs["transport_distance"] = transport_distance * inputs["circuity_ratio"]

        outputs["CapEx"] = (
            commodity_transported * outputs["transport_distance"] * inputs["unit_capex"]
        )
        outputs["OpEx"] = (
            commodity_transported * outputs["transport_distance"] * inputs["unit_fixed_opex"]
        )
