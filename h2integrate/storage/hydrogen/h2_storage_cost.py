import numpy as np
from attrs import field, define
from openmdao.utils import units

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import contains, gte_zero, range_val
from h2integrate.core.model_baseclasses import CostModelBaseClass
from h2integrate.storage.hydrogen.h2_transport.h2_compression import Compressor


@define(kw_only=True)
class HydrogenStorageBaseCostModelConfig(BaseConfig):
    """Base config class for HydrogenStorageBaseCostModel.

    Attributes:
        max_capacity (float): Maximum storage capacity (kg)
        max_charge_rate (float): Maximum charging rate (kg/h)
        sizing_mode (str): Mode for sizing storage (auto or set)
        commodity_rate_units (str): Units of the commodity
        cost_year (int): Year for cost calculations
        labor_rate (float): Labor rate for cost calculations
        insurance (float): Insurance cost as a fraction of total cost
        property_taxes (float): Property taxes as a fraction of total cost
        licensing_permits (float): Licensing and permits cost as a fraction of total cost
        compressor_om (float): Compressor operation and maintenance cost as a fraction of total cost
        facility_om (float): Facility operation and maintenance cost as a fraction of total cost
        inlet_pressure_bar (float): Inlet pressure for compressed gas storage (bar)
        storage_pressure_bar (float): Storage pressure for compressed gas storage (bar) - max 700
        cg_capex_per_kg_350_bar (float): Capital cost per kg for compressed gas storage at 350 bar
            Default is $1200 (2013 dollars) from HDSAM, converted to 2018 dollars using CEPCI.
        cg_capex_per_kg_700_bar (float): Capital cost per kg for compressed gas storage at 700 bar
            Default is $1800 (2013 dollars) from HDSAM, converted to 2018 dollars using CEPCI.
    """

    max_capacity: float | None = field(default=None)
    max_charge_rate: float | None = field(default=None)
    sizing_mode: str = field(
        default="set", converter=(str.strip, str.lower), validator=contains(["auto", "set"])
    )

    commodity_rate_units: str = field(default="kg/h", validator=contains(["kg/h", "g/h", "t/h"]))

    cost_year: int = field(default=2018, converter=int, validator=contains([2018]))
    labor_rate: float = field(default=37.39817, validator=gte_zero)
    insurance: float = field(default=0.01, validator=range_val(0, 1))
    property_taxes: float = field(default=0.01, validator=range_val(0, 1))
    licensing_permits: float = field(default=0.001, validator=range_val(0, 1))
    compressor_om: float = field(default=0.04, validator=range_val(0, 1))
    facility_om: float = field(default=0.01, validator=range_val(0, 1))
    inlet_pressure_bar: float = field(default=20, validator=gte_zero)
    storage_pressure_bar: float = field(default=200, validator=range_val(0, 700))
    cg_capex_per_kg_350_bar: float = field(default=1333.11625, validator=gte_zero)
    cg_capex_per_kg_700_bar: float = field(default=1999.67437, validator=gte_zero)

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
            "commodity_rate_units",
            "cost_year",
        ]
        lrc_dict = {k: v for k, v in params.items() if k not in h2i_params}
        return lrc_dict


class HydrogenStorageBaseCostModel(CostModelBaseClass):
    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def initialize(self):
        super().initialize()

    def setup(self):
        self.config = HydrogenStorageBaseCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            strict=False,
            additional_cls_name=self.__class__.__name__,
        )

        n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]

        super().setup()

        self.add_input(
            "max_charge_rate",
            val=self.config.max_charge_rate,
            units=f"{self.config.commodity_rate_units}",
            desc="Hydrogen storage charge rate",
        )

        self.add_input(
            "storage_capacity",
            val=self.config.max_capacity,
            units=f"{self.config.commodity_rate_units}*h",
            desc="Hydrogen storage capacity",
        )

        self.add_input(
            "hydrogen_in",
            val=0.0,
            shape=n_timesteps,
            units=f"{self.config.commodity_rate_units}",
            desc="Hydrogen input timeseries for average flow rate calculation",
        )

    def make_storage_input_dict(self, inputs):
        storage_input = {}

        storage_input = self.config.make_model_dict()

        # convert capacity to kg
        max_capacity_kg = units.convert_units(
            inputs["storage_capacity"], f"({self.config.commodity_rate_units})*h", "kg"
        )

        storage_input["h2_storage_kg"] = max_capacity_kg[0]

        # system_flow_rate must be in kg/day.
        # Per HDSAM (Papadias 2021), system_flow_rate is the average flow rate,
        # not the maximum fill rate.
        avg_hydrogen_in = np.mean(inputs["hydrogen_in"])
        system_flow_rate = units.convert_units(
            avg_hydrogen_in, f"{self.config.commodity_rate_units}", "kg/d"
        )
        storage_input["system_flow_rate"] = system_flow_rate  # kg/day

        return storage_input

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # storage_input = self.make_storage_input_dict(inputs)

        raise NotImplementedError("This method should be implemented in a subclass.")


class LinedRockCavernStorageCostModel(HydrogenStorageBaseCostModel):
    """Capital and operational cost model for lined rock cavern hydrogen storage.

    Costs are in 2018 USD. Operational dynamics are not yet included.

    References:
        [1] Papadias 2021: https://www.sciencedirect.com/science/article/pii/S0360319921030834?via%3Dihub
        [2] Papadias 2021: Bulk Hydrogen as Function of Capacity.docx documentation at
            hydrogen_storage.md in the docs
        [3] HDSAM V4.0 Gaseous H2 Geologic Storage sheet
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Calculate installed capital and O&M costs for lined rock cavern hydrogen storage.

        Args:
            inputs: OpenMDAO inputs containing ``max_capacity`` (total capacity [kg]),
                ``max_charge_rate`` (charge rate [kg/h]), and ``hydrogen_in``
                (timeseries [kg/h]).
            outputs: OpenMDAO outputs dict.
            discrete_inputs: OpenMDAO discrete inputs dict.
            discrete_outputs: OpenMDAO discrete outputs dict.

        Sets:
            outputs["CapEx"]: Installed capital cost in 2018 USD (including compressor).
            outputs["OpEx"]: Annual fixed O&M in 2018 USD/yr (excluding electricity).

        Notes:
            Additional parameters from ``storage_input``:

            - h2_storage_kg (float): Total capacity of hydrogen storage [kg].
            - system_flow_rate (float): Average flow rate [kg/day].
            - labor_rate (float): Labor rate, default 37.40 [$2018/hr].
            - insurance (float): Fraction of total investment, default 1%.
            - property_taxes (float): Fraction of total investment, default 1%.
            - licensing_permits (float): Fraction of total investment, default 0.1%.
            - compressor_om (float): Fraction of compressor investment, default 4%.
            - facility_om (float): Fraction of facility investment minus compressor, default 1%.
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
        comp_type = "pipeline"
        storage_compressor = Compressor(
            outlet_pressure,
            system_flow_rate,
            n_compressors=n_compressors,
            compressor_type=comp_type,
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
    """Capital and operational cost model for salt cavern hydrogen storage.

    Costs are in 2018 USD. Operational dynamics are not yet included.

    References:
        [1] Papadias 2021: https://www.sciencedirect.com/science/article/pii/S0360319921030834?via%3Dihub
        [2] Papadias 2021: Bulk Hydrogen as Function of Capacity.docx documentation at
            hydrogen_storage.md in the docs
        [3] HDSAM V4.0 Gaseous H2 Geologic Storage sheet
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Calculate installed capital and O&M costs for salt cavern hydrogen storage.

        Args:
            inputs: OpenMDAO inputs containing ``max_capacity`` (total capacity [kg]),
                ``max_charge_rate`` (charge rate [kg/h]), and ``hydrogen_in``
                (timeseries [kg/h]).
            outputs: OpenMDAO outputs dict.
            discrete_inputs: OpenMDAO discrete inputs dict.
            discrete_outputs: OpenMDAO discrete outputs dict.

        Sets:
            outputs["CapEx"]: Installed capital cost in 2018 USD (including compressor).
            outputs["OpEx"]: Annual fixed O&M in 2018 USD/yr (excluding electricity).

        Notes:
            Additional parameters from ``storage_input``:

            - h2_storage_kg (float): Total capacity of hydrogen storage [kg].
            - system_flow_rate (float): Average flow rate [kg/day].
            - labor_rate (float): Labor rate, default 37.40 [$2018/hr].
            - insurance (float): Fraction of total investment, default 1%.
            - property_taxes (float): Fraction of total investment, default 1%.
            - licensing_permits (float): Fraction of total investment, default 0.1%.
            - compressor_om (float): Fraction of compressor investment, default 4%.
            - facility_om (float): Fraction of facility investment minus compressor, default 1%.
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
        comp_type = "pipeline"
        storage_compressor = Compressor(
            outlet_pressure,
            system_flow_rate,
            n_compressors=n_compressors,
            compressor_type=comp_type,
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
    """Capital and operational cost model for underground pipeline hydrogen storage.

    Costs are in 2018 USD. Operational dynamics and physical size (footprint and
    mass) are not yet included.

    Notes:
        - Oversize pipe: pipe OD = 24" schedule 60 [1].
        - Max pressure: 100 bar.

    References:
        [1] Papadias 2021: https://www.sciencedirect.com/science/article/pii/S0360319921030834?via%3Dihub
        [2] Papadias 2021: Bulk Hydrogen as Function of Capacity.docx documentation at
            hydrogen_storage.md in the docs
        [3] HDSAM V4.0 Gaseous H2 Geologic Storage sheet
    """

    _time_step_bounds = (
        3600,
        3600,
    )  # (min, max) time step lengths (in seconds) compatible with this model

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Calculate installed capital and O&M costs for underground pipe hydrogen storage.

        Args:
            inputs: OpenMDAO inputs containing ``max_capacity`` (total capacity [kg]),
                ``max_charge_rate`` (charge rate [kg/h]), and ``hydrogen_in``
                (timeseries [kg/h]).
            outputs: OpenMDAO outputs dict.
            discrete_inputs: OpenMDAO discrete inputs dict.
            discrete_outputs: OpenMDAO discrete outputs dict.

        Sets:
            outputs["CapEx"]: Installed capital cost in 2018 USD (including compressor).
            outputs["OpEx"]: Annual fixed O&M in 2018 USD/yr (excluding electricity).

        Notes:
            - Oversize pipe: pipe OD = 24" schedule 60.
            - Max pressure: 100 bar.
            - ``compressor_output_pressure`` must be 100 bar for underground pipe storage.

            Additional parameters from ``storage_input``:

            - h2_storage_kg (float): Total capacity of hydrogen storage [kg].
            - system_flow_rate (float): Average flow rate [kg/day].
            - labor_rate (float): Labor rate, default 37.40 [$2018/hr].
            - insurance (float): Fraction of total investment, default 1%.
            - property_taxes (float): Fraction of total investment, default 1%.
            - licensing_permits (float): Fraction of total investment, default 0.1%.
            - compressor_om (float): Fraction of compressor investment, default 4%.
            - facility_om (float): Fraction of facility investment minus compressor, default 1%.
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
        comp_type = "pipeline"
        storage_compressor = Compressor(
            outlet_pressure,
            system_flow_rate,
            n_compressors=n_compressors,
            compressor_type=comp_type,
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


class CompressedGasStorageCostModel(HydrogenStorageBaseCostModel):
    """Capital and operational cost model for compressed gas hydrogen storage.

    This model is based on HDSAM's compressed gas hydrogen storage terminal cost model, which is
    designed for loading of trucks with compressed H2. In this model, we isolate just the parts of
    the HDSAM that relate to filling and storage, and ignoring the costs related to truck loading.

    Costs have been converted to 2018 costs to match the models above using CEPCI values in HDSAM.

    References:
        [1] HDSAM V5.5 Compressed Gas H2 Terminal: https://hdsam.es.anl.gov/index.php?content=hdsam
    """

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """Calculate installed capital and O&M costs for lined rock cavern hydrogen storage.

        Args:
            inputs: OpenMDAO inputs containing ``max_capacity`` (total capacity [kg]),
                ``max_charge_rate`` (charge rate [kg/h]), and ``hydrogen_in``
                (timeseries [kg/h]).
            outputs: OpenMDAO outputs dict.
            discrete_inputs: OpenMDAO discrete inputs dict.
            discrete_outputs: OpenMDAO discrete outputs dict.

        Sets:
            outputs["CapEx"]: Installed capital cost in 2018 USD (including compressor).
            outputs["OpEx"]: Annual fixed O&M in 2018 USD/yr (excluding electricity).
        """

        # ============================================================================
        # Design inputs
        # ============================================================================
        # Relevant design parameters (mostly rows 32-74 of "Compressed Gas H2 Terminal" in [1])

        h2_in_kg_d = units.convert_units(
            inputs["hydrogen_in"], f"({self.config.commodity_rate_units})", "kg/d"
        )
        terminal_capacity_kg_d = np.max(h2_in_kg_d)
        storage_capacity_kg = units.convert_units(
            inputs["storage_capacity"][0], f"({self.config.commodity_rate_units})*h", "kg"
        )
        n_compressors = np.ceil(terminal_capacity_kg_d / 24 / 50)  # Cell B59
        # Not sure where the 50 comes from in HDSAM - using rule of thumb of 1 unit per 50 kg/hr?
        storage_compressor = Compressor(
            compressor_type="storage",
            p_inlet=self.config.inlet_pressure_bar,
            p_outlet=self.config.storage_pressure_bar,
            flow_rate_kg_d=terminal_capacity_kg_d,
            n_compressors=n_compressors,
        )

        # ============================================================================
        # Calculate CAPEX
        # ============================================================================
        # Installed capital cost per kg from rows 158-180 of "Compressed Gas H2 Terminal" in [1]
        # Capex for compressor and storage scales with size
        # Capex for piping, plumbing, electrical, instrumentation, and buildings is constant
        # CEPCI data from HDSAM used to convert most costs to 2018, for those without a CEPCI index
        # the BLS CPI calcualtor was used instead: https://data.bls.gov/cgi-bin/cpicalc.pl
        # "Truck Loading Compressor" and "Truck Scale" from HDSAM are not included

        # Storage Compressor
        storage_compressor.compressor_power()
        unit_power_kw, system_power_kw = storage_compressor.compressor_system_power()
        comp_capex_2016, _ = storage_compressor.compressor_costs()
        comp_capex = comp_capex_2016 * 1.36013289036545 / 1.2890365448505
        # Values taken from CEPCI table in "Feedstock & Utility Prices"

        # Compressed Gas H2 Storage
        # Currently using a linear fit between 350 and 700 bar (the two discrete HDSAM levels)
        # Fit is coming from config values which are already in 2018 dollars
        capex_per_kg_350_bar = self.config.cg_capex_per_kg_350_bar  # "Cost Data" row 89
        capex_per_kg_700_bar = self.config.cg_capex_per_kg_700_bar  # "Cost Data" row 96
        tank_capex_per_kg = (
            capex_per_kg_350_bar
            + (capex_per_kg_700_bar - capex_per_kg_350_bar)
            * (self.config.storage_pressure_bar - 350)
            / 350
        )
        tank_installation_factor = 1.3
        tank_capex = tank_capex_per_kg * storage_capacity_kg * tank_installation_factor

        # Piping - simplifying a bit from HDSAM since this is a "drop in the bucket"
        kg_d_per_pipe_m = 300  # Estimated by dividing B34 by B104 for many different values
        pipe_length_m = terminal_capacity_kg_d / kg_d_per_pipe_m  # Simplifying calc of B104
        pipe_capex_per_m_2005 = 300  # Using H2A "Estimate based on engineering judgement"
        pipe_capex_2005 = pipe_length_m * pipe_capex_per_m_2005
        pipe_capex = pipe_capex_2005 * 1.53471220137887 / 1.0

        # Plumbing, electrical, instrumentation capex = "pei" - simplifying a bit from HDSAM
        kg_d_per_bay = 1600  # Estimated by dividing B34 by B103 for many different values
        num_bays = terminal_capacity_kg_d / kg_d_per_bay  # Simplifying calc of B103
        pipe_capex_per_bay_2005 = 10000  # Using H2A "Estimate based on engineering judgement"
        pei_capex_2005 = num_bays * pipe_capex_per_bay_2005
        pei_capex = pei_capex_2005 * 2.0454178984144 / 1.0

        # Buildings and structures
        buildings_capex_2022 = 370029
        buildings_capex = buildings_capex_2022 * 1.33340822287126 / 1.85014603459897

        # Land - simplifying
        kg_d_per_land_m2 = 4  # Estimated by dividing B34 by B192 for many different values
        land_required_m2 = terminal_capacity_kg_d / kg_d_per_land_m2
        land_capex_per_m2_2022 = 12.35
        land_capex_2022 = land_required_m2 * land_capex_per_m2_2022
        land_capex = land_capex_2022 * 0.88  # Using CPI to convert to 2018 no CEPCI for land)

        # Other
        depreciable_capex = comp_capex + tank_capex + pipe_capex + pei_capex + buildings_capex
        site_preparation_pct = 0.05
        engineering_design_pct = 0.1
        project_contingency_pct = 0.1
        licensing_pct = 0.0
        permitting_pct = 0.03
        owner_cost_pct = 0.12
        total_other_capex_pct = (
            site_preparation_pct
            + engineering_design_pct
            + project_contingency_pct
            + licensing_pct
            + permitting_pct
            + owner_cost_pct
        )
        other_capex_2022 = depreciable_capex * total_other_capex_pct
        other_capex = other_capex_2022 * 0.88  # Using CPI to convert to 2018

        # Final, total installed cost:
        installed_capex = depreciable_capex + land_capex + other_capex

        # ============================================================================
        # Calculate OPEX
        # ============================================================================
        # Operations and Maintenance costs [1]

        # Labor
        # Base case is 2 operators, 24 hours a day, 7 days a week for a 100,000 kg/day
        # average capacity facility. Scaling factor of 0.25 is used for other sized facilities
        # See equation on HDSAM "Cost Data" tab, row 12
        # Cost corrected to 2018 using HDSAM "Feedstock & Utility Prices" tab, Table B3
        system_flow_rate = terminal_capacity_kg_d
        annual_hours = 2 * 8760 * (system_flow_rate / 100000) ** 0.25
        labor_rate_2013 = 27.51
        labor_rate = labor_rate_2013 * 1.29 / 1.09
        overhead = 0.5
        labor_om = annual_hours * labor_rate * overhead

        # Other O&M
        insurance_pct = self.config.insurance
        property_taxes_pct = self.config.property_taxes
        licensing_permits_pct = self.config.licensing_permits
        comp_om_pct = self.config.compressor_om
        facility_om_pct = self.config.facility_om
        insurance_om = insurance_pct * installed_capex
        property_taxes_om = property_taxes_pct * installed_capex
        licensing_permits_om = licensing_permits_pct * installed_capex
        comp_om = comp_om_pct * comp_capex
        facility_om = facility_om_pct * (installed_capex - comp_capex)

        # O&M excludes electricity requirements
        total_om = (
            labor_om
            + insurance_om
            + licensing_permits_om
            + property_taxes_om
            + comp_om
            + facility_om
        )

        outputs["CapEx"] = installed_capex
        outputs["OpEx"] = total_om
