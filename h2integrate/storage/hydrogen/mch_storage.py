import numpy as np
from attrs import field, define
from openmdao.utils import units

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains
from h2integrate.core.model_baseclasses import CostModelBaseClass


@define(kw_only=True)
class MCHTOLStorageCostModelConfig(BaseConfig):
    """Config class for MCHTOLStorageCostModel

    Attributes:
        max_capacity (float): Maximum hydrogen storage capacity (in non-rate units,
            e.g., "kg" if `commodity_units` is "kg/h").
        max_charge_rate (float): Maximum rate at which the commodity can be charged (in units
            per time step, e.g., "kg/time step"). This is the hydrogenation capacity.
        charge_equals_discharge (bool, optional): If True, set the max_discharge_rate equal to the
            max_charge_rate. If False, specify the max_discharge_rate as a value different than
            the max_charge_rate. Defaults to True. This is the dehydrogenation capacity.
        max_discharge_rate (float | None, optional): Maximum rate at which the commodity can be
            discharged (in units per time step, e.g., "kg/time step"). This rate does not include
            the discharge_efficiency. Only required if `charge_equals_discharge` is False.
        commodity_name (str, optional): Name of the commodity being controlled (e.g., "hydrogen").
            Defaults to "hydrogen"
        commodity_units (str, optional): Units of the commodity (e.g., "kg/h"). Defaults to "kg/h"
        cost_year (int, optional): Dollar year corresponding to the costs, must be 2024.
    """

    max_capacity: float = field()
    max_charge_rate: float = field()
    max_discharge_rate: float = field(default=None)
    charge_equals_discharge: bool = field(default=True)

    commodity_name: str = field(default="hydrogen")
    commodity_units: str = field(default="kg/h", validator=contains(["kg/h", "g/h", "t/h"]))

    cost_year: int = field(default=2024, converter=int, validator=contains([2024]))

    def __attrs_post_init__(self):
        if self.charge_equals_discharge:
            if (
                self.max_discharge_rate is not None
                and self.max_discharge_rate != self.max_charge_rate
            ):
                msg = (
                    "Max discharge rate does not equal max charge rate but charge_equals_discharge "
                    f"is True. Discharge rate is {self.max_discharge_rate} and charge rate "
                    f"is {self.max_charge_rate}."
                )
                raise ValueError(msg)

            self.max_discharge_rate = self.max_charge_rate


class MCHTOLStorageCostModel(CostModelBaseClass):
    """
    Cost model representing a toluene/methylcyclohexane (TOL/MCH) hydrogen storage system.

    Costs are in 2024 USD.

    Sources:
        Breunig, H., Rosner, F., Saqline, S. et al. "Achieving gigawatt-scale green hydrogen
        production and seasonal storage at industrial locations across the U.S." *Nat Commun*
        **15**, 9049 (2024). https://doi.org/10.1038/s41467-024-53189-2

    """

    def initialize(self):
        super().initialize()

    def setup(self):
        self.config = MCHTOLStorageCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=False,
        )

        super().setup()

        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=f"{self.config.commodity_units}",
            desc="Hydrogen storage charge rate",
        )

        if self.config.charge_equals_discharge:
            self.add_input(
                "max_discharge_rate",
                val=self.config.max_charge_rate,
                units=f"{self.config.commodity_units}",
                desc="Hydrogen storage discharge rate",
            )
        else:
            self.add_input(
                "max_discharge_rate",
                val=self.config.max_discharge_rate,
                units=f"{self.config.commodity_units}",
                desc="Hydrogen storage discharge rate",
            )

        self.add_input(
            "max_capacity",
            val=self.config.max_capacity,
            units=f"{self.config.commodity_units}*h",
            desc="Hydrogen storage capacity",
        )

        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        self.add_input(
            "hydrogen_soc",
            units="unitless",
            val=0.0,
            shape=self.n_timesteps,
            desc="Hydrogen state of charge timeseries for storage",
        )

    def calc_cost_value(self, b0, b1, b2, b3, b4):
        """
        Calculate the value of the cost function for the given coefficients.

        Args:
            b0 (float): Coefficient representing the base cost.
            b1 (float): Coefficient for the Hc (hydrogenation capacity) term.
            b2 (float): Coefficient for the Dc (dehydrogenation capacity) term.
            b3 (float): Coefficient for the Ms (maximum storage) term.
            b4 (float): Coefficient for the As (annual hydrogen into storage) term.
        Returns:
            float: The calculated cost value based on the provided coefficients and attributes.

        """
        return b0 + (b1 * self.Hc) + (b2 * self.Dc) + (b3 * self.Ms) + b4 * self.As

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # convert charge rate to kg/d
        storage_max_fill_rate_tpd = units.convert_units(
            inputs["max_charge_rate"], f"{self.config.commodity_units}", "t/d"
        )

        # convert discharge rate to kg/d
        if self.config.charge_equals_discharge:
            storage_max_empty_rate_tpd = units.convert_units(
                inputs["max_charge_rate"], f"{self.config.commodity_units}", "t/d"
            )
        else:
            storage_max_empty_rate_tpd = units.convert_units(
                inputs["max_discharge_rate"], f"{self.config.commodity_units}", "t/d"
            )

        # convert state of charge profile from fraction to kg
        hydrogen_storage_soc_kg = units.convert_units(
            inputs["hydrogen_soc"] * inputs["max_capacity"],
            f"({self.config.commodity_units})*h",
            "kg",
        )

        # calculate the annual amount of hydrogen stored
        h2_charge_discharge = np.diff(hydrogen_storage_soc_kg, prepend=False)
        h2_charged_idx = np.argwhere(h2_charge_discharge > 0).flatten()
        annual_h2_stored_kg = sum([h2_charge_discharge[i] for i in h2_charged_idx])

        # convert annual hydrogen stored to metric tonnes/day
        annual_h2_stored_tpy = units.convert_units(
            annual_h2_stored_kg,
            "kg/yr",
            "t/yr",
        )

        h2_storage_capacity_tons = units.convert_units(
            inputs["max_capacity"], f"({self.config.commodity_units})*h", "t"
        )

        # hydrogenation capacity [metric tonnes/day]
        self.Hc = storage_max_fill_rate_tpd[0]

        # dehydrogenation capacity [metric tonnes/day]
        self.Dc = storage_max_empty_rate_tpd[0]

        # annual hydrogen into storage [metric tonnes]
        self.As = annual_h2_stored_tpy  # tons/year

        # maximum storage capacity [metric tonnes]
        self.Ms = h2_storage_capacity_tons[0]

        # overnight capital cost coefficients
        occ_coeff = (54706639.43, 147074.25, 588779.05, 20825.39, 10.31)

        # fixed O&M cost coefficients
        foc_coeff = (3419384.73, 3542.79, 13827.02, 61.22, 0.0)

        # variable O&M cost coefficients
        voc_coeff = (711326.78, 1698.76, 6844.86, 36.04, 376.31)

        outputs["CapEx"] = self.calc_cost_value(*occ_coeff)
        outputs["OpEx"] = self.calc_cost_value(*foc_coeff)
        outputs["VarOpEx"] = self.calc_cost_value(*voc_coeff)
