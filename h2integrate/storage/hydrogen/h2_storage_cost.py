import numpy as np
from attrs import field, define
from openmdao.utils import units

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, gte_zero, range_val
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.storage.hydrogen.h2_transport.h2_compression import Compressor


@define(kw_only=True)
class HydrogenStorageBaseCostModelConfig(BaseConfig):
    """Base config class for HydrogenStorageBaseCostModel

    Attributes:
        max_capacity (float): Maximum hydrogen storage capacity (in non-rate units,
            e.g., "kg" if `commodity_units` is "kg/h").
        max_charge_rate (float): Maximum rate at which the commodity can be charged (in units
            per time step, e.g., "kg/time step"). This is the hydrogenation capacity.
        commodity_name (str, optional): Name of the commodity being controlled (e.g., "hydrogen").
            Defaults to "hydrogen"
        commodity_units (str, optional): Units of the commodity (e.g., "kg/h"). Defaults to "kg/h"
        cost_year (int, optional): Dollar year corresponding to the costs, must be 2018.
        labor_rate (float, optional): hourly cost of labor in 2018 USD/hr. Defaults to 37.39817.
        insurance_rate (float, optional): insurance cost as a percent (between 0 and 1) of
            storage capex. Defaults to 0.01 (or 1.0%).
        property_taxes (float, optional): property tax cost as a percent (between 0 and 1) of
            storage capex. Defaults to 0.01 (or 1.0%).
        licensing_permits (float, optional): licensing and permitting costs as a percent
            (between 0 and 1) of storage capex. Defaults to 0.001 (or 0.1%).
        compressor_om (float, optional): Compressor fixed operations and maintenance cost as a
            percent (between 0 and 1) of compressor capex. Defaults to 0.04 (or 4.0%).
        facility_om (float, optional):
    """

    max_capacity: float | None = field(default=None)
    max_charge_rate: float | None = field(default=None)
    sizing_mode: str = field(
        default="set", converter=(str.strip, str.lower), validator=contains(["auto", "set"])
    )

    commodity_name: str = field(default="hydrogen")
    commodity_units: str = field(default="kg/h", validator=contains(["kg/h", "g/h", "t/h"]))

    cost_year: int = field(default=2018, converter=int, validator=contains([2018]))
    labor_rate: float = field(default=37.39817, validator=gte_zero)
    insurance: float = field(default=0.01, validator=range_val(0, 1))
    property_taxes: float = field(default=0.01, validator=range_val(0, 1))
    licensing_permits: float = field(default=0.001, validator=range_val(0, 1))
    compressor_om: float = field(default=0.04, validator=range_val(0, 1))
    facility_om: float = field(default=0.01, validator=range_val(0, 1))

    def __attrs_post_init__(self):
        undefined_capacities = self.max_capacity is None or self.max_charge_rate is None
        if undefined_capacities and self.sizing_mode == "set":
            msg = (
                "Missing storage attribute(s): max_capacity and/or max_charge_rate, "
                "for the cost_parameters. These attributes are required if `sizing_mode` "
                "is 'set'. If storage will be auto-sized by the performance model, set the "
                "`sizing_mode` cost parameter to 'auto'."
            )
            raise ValueError(msg)
        if not undefined_capacities and self.sizing_mode == "auto":
            msg = (
                "Extra storage attribute(s) found: max_capacity and/or max_charge_rate, "
                "for the cost_parameters. These attributes should not be defined if `sizing_mode` "
                "is 'auto'. If storage will be auto-sized by the performance model, set the "
                "`sizing_mode` cost parameter to 'auto' and do not include max_capacity or "
                "max_charge_rate and a cost parameter. Set `sizing_mode` to 'set' if the storage "
                "capacity is fixed."
            )
            raise ValueError(msg)

        if undefined_capacities and self.sizing_mode == "auto":
            # set to zero for initialization in setup().
            self.max_capacity = 0.0
            self.max_charge_rate = 0.0

    def make_model_dict(self):
        params = self.as_dict()
        h2i_params = [
            "max_capacity",
            "max_charge_rate",
            "commodity_name",
            "commodity_units",
            "cost_year",
        ]
        lrc_dict = {k: v for k, v in params.items() if k not in h2i_params}
        return lrc_dict


class HydrogenStorageBaseCostModel(CostModelBaseClass):
    def initialize(self):
        super().initialize()

    def setup(self):
        self.config = HydrogenStorageBaseCostModelConfig.from_dict(
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

        self.add_input(
            "max_capacity",
            val=self.config.max_capacity,
            units=f"{self.config.commodity_units}*h",
            desc="Hydrogen storage capacity",
        )

    def make_storage_input_dict(self, inputs):
        storage_input = {}

        storage_input = self.config.make_model_dict()

        # convert capacity to kg
        max_capacity_kg = units.convert_units(
            inputs["max_capacity"], f"({self.config.commodity_units})*h", "kg"
        )

        # convert charge rate to kg/day (required for storage models)
        storage_max_fill_rate = units.convert_units(
            inputs["max_charge_rate"], f"{self.config.commodity_units}", "kg/d"
        )

        storage_input["h2_storage_kg"] = max_capacity_kg[0]

        # system_flow_rate must be in kg/day
        storage_input["system_flow_rate"] = storage_max_fill_rate[0]  # kg/day

        return storage_input

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # storage_input = self.make_storage_input_dict(inputs)

        raise NotImplementedError("This method should be implemented in a subclass.")


class LinedRockCavernStorageCostModel(HydrogenStorageBaseCostModel):
    """
    Author: Kaitlin Brunik
    Created: 7/20/2023
    Institution: National Renewable Energy Lab
    Description: This file outputs capital and operational costs of lined rock cavern
    hydrogen storage.
    It needs to be updated to with operational dynamics.
    Costs are in 2018 USD

    Sources:
        - [1] Papadias 2021: https://www.sciencedirect.com/science/article/pii/S0360319921030834?via%3Dihub
        - [2] Papadias 2021: Bulk Hydrogen as Function of Capacity.docx documentation at
              hydrogen_storage.md in the docs
        - [3] HDSAM V4.0 Gaseous H2 Geologic Storage sheet
    """

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Calculates the installed capital cost and operation and maintenance costs for lined rock
        cavern hydrogen storage.

        Args:
            inputs: OpenMDAO inputs containing:
                - max_capacity: total capacity of hydrogen storage [kg]
                - max_charge_rate: hydrogen storage charge rate [kg/h]

        Returns via outputs:
            - CapEx (float): the installed capital cost in 2018 [USD] (including compressor)
            - OpEx (float): the OPEX (annual, fixed) in 2018 excluding electricity costs [USD/yr]

        Additional parameters from storage_input:
            - h2_storage_kg (float): total capacity of hydrogen storage [kg]
            - system_flow_rate (float): [kg/day]
            - labor_rate (float): (default: 37.40) [$2018/hr]
            - insurance (float): (default: 1%) [decimal percent] - % of total investment
            - property_taxes (float): (default: 1%) [decimal percent] - % of total investment
            - licensing_permits (float): (default: 0.1%) [decimal percent] - % of total investment
            - compressor_om (float): (default: 4%) [decimal percent] - % of compressor investment
            - facility_om (float): (default: 1%) [decimal percent] - % of facility investment
                minus compressor investment
        """
        storage_input = self.make_storage_input_dict(inputs)

        # Extract input parameters
        h2_storage_kg = storage_input["h2_storage_kg"]  # [kg]
        system_flow_rate = storage_input["system_flow_rate"]  # [kg/day]
        labor_rate = storage_input.get("labor_rate", 37.39817)  # $(2018)/hr
        insurance = storage_input.get("insurance", 1 / 100)  # % of total capital investment
        property_taxes = storage_input.get(
            "property_taxes", 1 / 100
        )  # % of total capital investment
        licensing_permits = storage_input.get(
            "licensing_permits", 0.1 / 100
        )  # % of total capital investment
        comp_om = storage_input.get("compressor_om", 4 / 100)  # % of compressor capital investment
        facility_om = storage_input.get(
            "facility_om", 1 / 100
        )  # % of facility capital investment minus compressor capital investment

        # ============================================================================
        # Calculate CAPEX
        # ============================================================================
        # Installed capital cost per kg from Papadias [2]
        # Coefficients for lined rock cavern storage cost equation
        a = 0.095803
        b = 1.5868
        c = 10.332
        # Calculate installed capital cost per kg using exponential fit
        lined_rock_cavern_storage_capex_per_kg = np.exp(
            a * (np.log(h2_storage_kg / 1000)) ** 2 - b * np.log(h2_storage_kg / 1000) + c
        )  # 2019 [USD] from Papadias [2]
        installed_capex = lined_rock_cavern_storage_capex_per_kg * h2_storage_kg
        cepci_overall = 1.29 / 1.30  # Convert from $2019 to $2018
        installed_capex = cepci_overall * installed_capex

        # ============================================================================
        # Calculate compressor costs
        # ============================================================================
        outlet_pressure = 200  # Max outlet pressure of lined rock cavern in [1] [bar]
        n_compressors = 2
        storage_compressor = Compressor(
            outlet_pressure, system_flow_rate, n_compressors=n_compressors
        )
        storage_compressor.compressor_power()
        motor_rating, power = storage_compressor.compressor_system_power()
        # Check if motor rating exceeds maximum, add additional compressor if needed
        if motor_rating > 1600:
            n_compressors += 1
            storage_compressor = Compressor(
                outlet_pressure, system_flow_rate, n_compressors=n_compressors
            )
            storage_compressor.compressor_power()
            motor_rating, power = storage_compressor.compressor_system_power()
        comp_capex, comp_OM = storage_compressor.compressor_costs()
        cepci = 1.36 / 1.29  # convert from $2016 to $2018
        comp_capex = comp_capex * cepci

        # ============================================================================
        # Calculate OPEX
        # ============================================================================
        # Operations and Maintenance costs [3]
        # Labor
        # Base case is 1 operator, 24 hours a day, 7 days a week for a 100,000 kg/day
        # average capacity facility. Scaling factor of 0.25 is used for other sized facilities
        annual_hours = 8760 * (system_flow_rate / 100000) ** 0.25
        overhead = 0.5
        labor = (annual_hours * labor_rate) * (1 + overhead)  # Burdened labor cost
        insurance_cost = insurance * installed_capex
        property_taxes_cost = property_taxes * installed_capex
        licensing_permits_cost = licensing_permits * installed_capex
        comp_op_maint = comp_om * comp_capex
        facility_op_maint = facility_om * (installed_capex - comp_capex)

        # O&M excludes electricity requirements
        total_om = (
            labor
            + insurance_cost
            + licensing_permits_cost
            + property_taxes_cost
            + comp_op_maint
            + facility_op_maint
        )

        outputs["CapEx"] = installed_capex
        outputs["OpEx"] = total_om


class SaltCavernStorageCostModel(HydrogenStorageBaseCostModel):
    """
    Author: Kaitlin Brunik
    Created: 7/20/2023
    Institution: National Renewable Energy Lab
    Description: This file outputs capital and operational costs of salt cavern hydrogen storage.
    It needs to be updated to with operational dynamics.
    Costs are in 2018 USD

    Sources:
        - [1] Papadias 2021: https://www.sciencedirect.com/science/article/pii/S0360319921030834?via%3Dihub
        - [2] Papadias 2021: Bulk Hydrogen as Function of Capacity.docx documentation at
              hydrogen_storage.md in the docs
        - [3] HDSAM V4.0 Gaseous H2 Geologic Storage sheet
    """

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Calculates the installed capital cost and operation and maintenance costs for salt cavern
        hydrogen storage.

        Args:
            inputs: OpenMDAO inputs containing:
                - max_capacity: total capacity of hydrogen storage [kg]
                - max_charge_rate: hydrogen storage charge rate [kg/h]

        Returns via outputs:
            - CapEx (float): the installed capital cost in 2018 [USD] (including compressor)
            - OpEx (float): the OPEX (annual, fixed) in 2018 excluding electricity costs [USD/yr]

        Additional parameters from storage_input:
            - h2_storage_kg (float): total capacity of hydrogen storage [kg]
            - system_flow_rate (float): [kg/day]
            - labor_rate (float): (default: 37.40) [$2018/hr]
            - insurance (float): (default: 1%) [decimal percent] - % of total investment
            - property_taxes (float): (default: 1%) [decimal percent] - % of total investment
            - licensing_permits (float): (default: 0.1%) [decimal percent] - % of total investment
            - compressor_om (float): (default: 4%) [decimal percent] - % of compressor investment
            - facility_om (float): (default: 1%) [decimal percent] - % of facility investment
                minus compressor investment
        """
        storage_input = self.make_storage_input_dict(inputs)

        # Extract input parameters
        h2_storage_kg = storage_input["h2_storage_kg"]  # [kg]
        system_flow_rate = storage_input["system_flow_rate"]  # [kg/day]
        labor_rate = storage_input.get("labor_rate", 37.39817)  # $(2018)/hr
        insurance = storage_input.get("insurance", 1 / 100)  # % of total capital investment
        property_taxes = storage_input.get(
            "property_taxes", 1 / 100
        )  # % of total capital investment
        licensing_permits = storage_input.get(
            "licensing_permits", 0.1 / 100
        )  # % of total capital investment
        comp_om = storage_input.get("compressor_om", 4 / 100)  # % of compressor capital investment
        facility_om = storage_input.get(
            "facility_om", 1 / 100
        )  # % of facility capital investment minus compressor capital investment

        # ============================================================================
        # Calculate CAPEX
        # ============================================================================
        # Installed capital cost per kg from Papadias [2]
        # Coefficients for salt cavern storage cost equation
        a = 0.092548
        b = 1.6432
        c = 10.161
        # Calculate installed capital cost per kg using exponential fit
        salt_cavern_storage_capex_per_kg = np.exp(
            a * (np.log(h2_storage_kg / 1000)) ** 2 - b * np.log(h2_storage_kg / 1000) + c
        )  # 2019 [USD] from Papadias [2]
        installed_capex = salt_cavern_storage_capex_per_kg * h2_storage_kg
        cepci_overall = 1.29 / 1.30  # Convert from $2019 to $2018
        installed_capex = cepci_overall * installed_capex

        # ============================================================================
        # Calculate compressor costs
        # ============================================================================
        outlet_pressure = 120  # Max outlet pressure of salt cavern in [1] [bar]
        n_compressors = 2
        storage_compressor = Compressor(
            outlet_pressure, system_flow_rate, n_compressors=n_compressors
        )
        storage_compressor.compressor_power()
        motor_rating, power = storage_compressor.compressor_system_power()
        # Check if motor rating exceeds maximum, add additional compressor if needed
        if motor_rating > 1600:
            n_compressors += 1
            storage_compressor = Compressor(
                outlet_pressure, system_flow_rate, n_compressors=n_compressors
            )
            storage_compressor.compressor_power()
            motor_rating, power = storage_compressor.compressor_system_power()
        comp_capex, comp_OM = storage_compressor.compressor_costs()
        cepci = 1.36 / 1.29  # convert from $2016 to $2018
        comp_capex = comp_capex * cepci

        # ============================================================================
        # Calculate OPEX
        # ============================================================================
        # Operations and Maintenance costs [3]
        # Labor
        # Base case is 1 operator, 24 hours a day, 7 days a week for a 100,000 kg/day
        # average capacity facility. Scaling factor of 0.25 is used for other sized facilities
        annual_hours = 8760 * (system_flow_rate / 100000) ** 0.25
        overhead = 0.5
        labor = (annual_hours * labor_rate) * (1 + overhead)  # Burdened labor cost
        insurance_cost = insurance * installed_capex
        property_taxes_cost = property_taxes * installed_capex
        licensing_permits_cost = licensing_permits * installed_capex
        comp_op_maint = comp_om * comp_capex
        facility_op_maint = facility_om * (installed_capex - comp_capex)

        # O&M excludes electricity requirements
        total_om = (
            labor
            + insurance_cost
            + licensing_permits_cost
            + property_taxes_cost
            + comp_op_maint
            + facility_op_maint
        )

        outputs["CapEx"] = installed_capex
        outputs["OpEx"] = total_om


class PipeStorageCostModel(HydrogenStorageBaseCostModel):
    """
    Author: Kaitlin Brunik
    Updated: 7/20/2023
    Institution: National Renewable Energy Lab
    Description: This file outputs capital and operational costs of underground pipeline hydrogen
    storage. It needs to be updated to with operational dynamics and physical size
    (footprint and mass).
    Oversize pipe: pipe OD = 24'' schedule 60 [1]
    Max pressure: 100 bar
    Costs are in 2018 USD

    Sources:
        - [1] Papadias 2021: https://www.sciencedirect.com/science/article/pii/S0360319921030834?via%3Dihub
        - [2] Papadias 2021: Bulk Hydrogen as Function of Capacity.docx documentation at
              hydrogen_storage.md in the docs
        - [3] HDSAM V4.0 Gaseous H2 Geologic Storage sheet
    """

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Calculates the installed capital cost and operation and maintenance costs for underground
        pipe hydrogen storage.

        Args:
            inputs: OpenMDAO inputs containing:
                - max_capacity: total capacity of hydrogen storage [kg]
                - max_charge_rate: hydrogen storage charge rate [kg/h]

        Returns via outputs:
            - CapEx (float): the installed capital cost in 2018 [USD] (including compressor)
            - OpEx (float): the OPEX (annual, fixed) in 2018 excluding electricity costs [USD/yr]

        Additional parameters from storage_input:
            - h2_storage_kg (float): total capacity of hydrogen storage [kg]
            - system_flow_rate (float): [kg/day]
            - labor_rate (float): (default: 37.40) [$2018/hr]
            - insurance (float): (default: 1%) [decimal percent] - % of total investment
            - property_taxes (float): (default: 1%) [decimal percent] - % of total investment
            - licensing_permits (float): (default: 0.1%) [decimal percent] - % of total investment
            - compressor_om (float): (default: 4%) [decimal percent] - % of compressor investment
            - facility_om (float): (default: 1%) [decimal percent] - % of facility investment
                minus compressor investment
        Notes:
            - Oversize pipe: pipe OD = 24'' schedule 60
            - Max pressure: 100 bar
            - compressor_output_pressure must be 100 bar for underground pipe storage
        """
        storage_input = self.make_storage_input_dict(inputs)

        # Extract input parameters
        h2_storage_kg = storage_input["h2_storage_kg"]  # [kg]
        system_flow_rate = storage_input["system_flow_rate"]  # [kg/day]
        labor_rate = storage_input.get("labor_rate", 37.39817)  # $(2018)/hr
        insurance = storage_input.get("insurance", 1 / 100)  # % of total capital investment
        property_taxes = storage_input.get(
            "property_taxes", 1 / 100
        )  # % of total capital investment
        licensing_permits = storage_input.get(
            "licensing_permits", 0.1 / 100
        )  # % of total capital investment
        comp_om = storage_input.get("compressor_om", 4 / 100)  # % of compressor capital investment
        facility_om = storage_input.get(
            "facility_om", 1 / 100
        )  # % of facility capital investment minus compressor capital investment

        # compressor_output_pressure must be 100 bar for underground pipe storage
        compressor_output_pressure = 100  # [bar]

        # ============================================================================
        # Calculate CAPEX
        # ============================================================================
        # Installed capital cost per kg from Papadias [2]
        # Coefficients for underground pipe storage cost equation
        a = 0.0041617
        b = 0.060369
        c = 6.4581
        # Calculate installed capital cost per kg using exponential fit
        pipe_storage_capex_per_kg = np.exp(
            a * (np.log(h2_storage_kg / 1000)) ** 2 - b * np.log(h2_storage_kg / 1000) + c
        )  # 2019 [USD] from Papadias [2]
        installed_capex = pipe_storage_capex_per_kg * h2_storage_kg
        cepci_overall = 1.29 / 1.30  # Convert from $2019 to $2018
        installed_capex = cepci_overall * installed_capex

        # ============================================================================
        # Calculate compressor costs
        # ============================================================================
        outlet_pressure = (
            compressor_output_pressure  # Max outlet pressure of underground pipe storage [1] [bar]
        )
        n_compressors = 2
        storage_compressor = Compressor(
            outlet_pressure, system_flow_rate, n_compressors=n_compressors
        )
        storage_compressor.compressor_power()
        motor_rating, power = storage_compressor.compressor_system_power()
        # Check if motor rating exceeds maximum, add additional compressor if needed
        if motor_rating > 1600:
            n_compressors += 1
            storage_compressor = Compressor(
                outlet_pressure, system_flow_rate, n_compressors=n_compressors
            )
            storage_compressor.compressor_power()
            motor_rating, power = storage_compressor.compressor_system_power()
        comp_capex, comp_OM = storage_compressor.compressor_costs()
        cepci = 1.36 / 1.29  # convert from $2016 to $2018
        comp_capex = comp_capex * cepci

        # ============================================================================
        # Calculate OPEX
        # ============================================================================
        # Operations and Maintenance costs [3]
        # Labor
        # Base case is 1 operator, 24 hours a day, 7 days a week for a 100,000 kg/day
        # average capacity facility. Scaling factor of 0.25 is used for other sized facilities
        annual_hours = 8760 * (system_flow_rate / 100000) ** 0.25
        overhead = 0.5
        labor = (annual_hours * labor_rate) * (1 + overhead)  # Burdened labor cost
        insurance_cost = insurance * installed_capex
        property_taxes_cost = property_taxes * installed_capex
        licensing_permits_cost = licensing_permits * installed_capex
        comp_op_maint = comp_om * comp_capex
        facility_op_maint = facility_om * (installed_capex - comp_capex)

        # O&M excludes electricity requirements
        total_om = (
            labor
            + insurance_cost
            + licensing_permits_cost
            + property_taxes_cost
            + comp_op_maint
            + facility_op_maint
        )

        outputs["CapEx"] = installed_capex
        outputs["OpEx"] = total_om
