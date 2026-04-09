import PySAM.MhkCosts as MhkCost
from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, contains, range_val, must_equal
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class PySAMMarineCostConfig(CostModelBaseConfig):
    """Configuration class for the PySAMMarineCostModel.

    Args:
        device_rating_kw (float): Rated power of the MHK device [kW]
        num_devices (int): Number of MHK tidal devices in the system
        reference_model_number (int): Reference model number from the
            Department of Energy Reference Model Project
            (1, 2, 3, 5 or 6).
        water_depth (float): Water depth in meters.
        distance_to_shore (float): Distance to shore in meters.
        number_rows (int): Number of rows in the device layout.
        device_spacing (float): Spacing between devices in a row in meters.
        row_spacing (float): Spacing between rows in meters.
        cable_system_overbuild: Cable system overbuild percentage.
        pysam_cost_options (dict, optional): dictionary of MhkCosts input parameters with
            top-level keys corresponding to the different MhkCosts variable groups.
            (please refer to MhkCosts documentation
            `here <https://nrel-pysam.readthedocs.io/en/main/modules/MhkCosts.html>`__
            )

        Note:
        More information about the reference models and their
        associated costs can be found in the
        [Reference Model Project](https://energy.sandia.gov/programs/renewable-energy/water-power/projects/reference-model-project-rmp/)

        The supported reference models in this cost model are:
            - Reference Model 1: Tidal Current Turbine
            - Reference Model 2: River Current Turbine
            - Reference Model 3: Wave Point Absorber
            - Reference Model 5: Oscillating Surge Flap
            - Reference Model 6: Oscillating Water Column

        Additional MHK cost model information can be found
        through the [System Advisor Model](https://sam.nlr.gov/)
    """

    device_rating_kw: float = field(validator=gt_zero)
    num_devices: int = field(validator=gt_zero)
    reference_model_number: int = field(validator=contains([1, 2, 3, 5, 6]))
    water_depth: float = field(validator=gt_zero)
    distance_to_shore: float = field(validator=gt_zero)
    number_rows: int = field(validator=gt_zero)
    device_spacing: float = field(validator=gt_zero)
    row_spacing: float = field(validator=gt_zero)
    cable_system_overbuild: float = field(validator=range_val(0, 100))
    pysam_cost_options: dict = field(default={})
    cost_year: int = field(
        default=2022, converter=int, validator=must_equal(2022)
    )  # TODO update based on feedback from SAM team

    def __attrs_post_init__(self):
        # if pysam_cost_options is not an empty dictionary
        if not self.pysam_cost_options:
            self.check_pysam_cost_options()

    def check_pysam_cost_options(self):
        """Checks that top-level keys of pysam_cost_options dictionary are valid and that
        system capacity is not given in pysam_cost_options.

        Raises:
           ValueError: if top-level keys of pysam_cost_options are not valid.
           ValueError: if device_rated_power is provide in pysam_cost_options["MHKCosts"]
        """
        valid_groups = [
            "MHKCosts",
        ]
        if bool(self.pysam_cost_options):
            invalid_groups = [k for k in self.pysam_cost_options if k not in valid_groups]
            if len(invalid_groups) > 0:
                msg = (
                    f"Invalid group(s) found in pysam_cost_options: {invalid_groups}. "
                    f"Valid groups are: {valid_groups}."
                )
                raise ValueError(msg)

            if (
                self.pysam_cost_options.get("MHKCosts", {}).get("device_rated_power", None)
                is not None
            ):
                msg = (
                    "Please do not specify device_rated_power in the pysam_cost_options "
                    "dictionary. The device rated power should be set with the "
                    "'device_rating' in the cost parameter."
                )
                raise ValueError(msg)
        return

    def create_input_dict(self):
        """Create dictionary of inputs to over-write the default values
            associated with the specified MHKCosts configuration.

        Returns:
           dict: dictionary of MHKCosts group parameters from user-input.
        """
        design_dict = {
            "MHKCosts": {
                "device_rated_power": self.device_rating_kw,
            },
        }

        # check if custom cost values are input
        cost_keys_map = [
            "structural_assembly_cost",
            "power_takeoff_system_cost",
            "mooring_found_substruc_cost",
            "development_cost",
            "eng_and_mgmt_cost",
            "assembly_and_install_cost",
            "other_infrastructure_cost",
            "array_cable_system_cost",
            "export_cable_system_cost",
            "onshore_substation_cost",
            "offshore_substation_cost",
            "other_elec_infra_cost",
        ]

        for key in cost_keys_map:
            design_dict["MHKCosts"][f"{key}_method"] = 2  # used modeled values
            design_dict["MHKCosts"][f"{key}_input"] = 0
            if self.pysam_cost_options.get("MHKCosts", {}).get(f"{key}_input", None) is not None:
                design_dict["MHKCosts"][f"{key}_method"] = self.pysam_cost_options.get(
                    "MHKCosts"
                ).get(f"{key}_input")
                design_dict["MHKCosts"][f"{key}_input"] = self.pysam_cost_options.get(
                    "MHKCosts"
                ).get(f"{key}_method")

        return design_dict


class PySAMMarineCostModel(CostModelBaseClass):
    """An OpenMDAO component for calculating the costs associated
    with Marine Hydrokinetic (MHK) energy systems.

    The class initializes and configures cost calculations for MHK systems.
        It uses the PySAM library for cost modeling which is based on industry
        input as well as the Department of Energy
        [Reference Model Project](https://energy.sandia.gov/programs/renewable-energy/water-power/projects/reference-model-project-rmp/).
        Additional MHK cost model information can be found
        through the [System Advisor Model](https://sam.nlr.gov/).

    Note:
        The supported reference models in this cost model are:
            - Reference Model 1: Tidal Current Turbine
            - Reference Model 2: River Current Turbine
            - Reference Model 3: Wave Point Absorber
            - Reference Model 5: Oscillating Surge Flap
            - Reference Model 6: Oscillating Water Column

    """

    def setup(self):
        self.config = PySAMMarineCostConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input(
            "device_rating",
            val=self.config.device_rating_kw,
            units="kW",
            desc="Rated power of the MHK device",
        )

        self.add_input(
            "num_devices",
            val=self.config.num_devices,
            units="unitless",
            desc="Number of MHK devices in the system",
        )

        self.cost_model = MhkCost.new()

        design_dict = self.config.create_input_dict()
        if bool(self.config.pysam_cost_options):
            for group, group_parameters in self.config.pysam_cost_options.items():
                if group in design_dict:
                    design_dict[group].update(group_parameters)
                else:
                    design_dict.update({group: group_parameters})
        self.cost_model.assign(design_dict)

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        # Assign
        number_devices = inputs["num_devices"][0]
        device_rating = inputs["device_rating"][0]
        self.cost_model.value("device_rated_power", device_rating)
        self.cost_model.value("system_capacity", device_rating * number_devices)

        if number_devices < self.config.number_rows:
            raise Exception("number_of_rows exceeds num_devices")
        else:
            if (number_devices / self.config.number_rows).is_integer():
                self.cost_model.value("devices_per_row", number_devices / self.config.number_rows)
            else:
                raise Exception(
                    "Layout must be square or rectangular. Modify 'number_rows' or 'num_devices'."
                )

        # Assign type of MHK device
        ref_model_num = f"RM{self.config.reference_model_number}"
        self.cost_model.value("lib_wave_device", ref_model_num)
        if ref_model_num == "RM3" or ref_model_num == "RM5" or ref_model_num == "RM6":
            self.cost_model.value("marine_energy_tech", 0)  # Wave
            self.cost_model.value("lib_wave_device", ref_model_num)
        elif ref_model_num == "RM1" or ref_model_num == "RM2":
            self.cost_model.value("marine_energy_tech", 1)  # Tidal
            self.cost_model.value("lib_tidal_device", ref_model_num)
        else:
            self.cost_model.value("marine_energy_tech", 0)  # Generic
        self.cost_model.value("library_or_input_wec", 0)

        # Inter-array cable length, m
        # The total length of cable used within the array of devices
        array_cable_length = (self.cost_model.value("devices_per_row") - 1) * (
            self.config.device_spacing * self.config.number_rows
        ) + self.config.row_spacing * (self.config.number_rows - 1)
        self.cost_model.value("inter_array_cable_length", array_cable_length)

        # Export cable length, m
        # The length of cable between the array and onshore grid connection point
        export_cable_length = (self.config.water_depth + self.config.distance_to_shore) * (
            1 + self.config.cable_system_overbuild / 100
        )
        self.cost_model.value("export_cable_length", export_cable_length)

        # Riser cable length, m
        # The length of cable from the seabed to the water surface that
        # connects the floating device to the seabed cabling.
        # Applies only to floating array
        riser_cable_length = (
            1.5
            * self.config.water_depth
            * number_devices
            * (1 + self.config.cable_system_overbuild / 100)
        )
        self.cost_model.value("riser_cable_length", riser_cable_length)

        self.cost_model.execute(1)

        cost_dict = self.cost_model.Outputs.export()

        capex = (
            cost_dict["structural_assembly_cost_modeled"]
            + cost_dict["power_takeoff_system_cost_modeled"]
            + cost_dict["mooring_found_substruc_cost_modeled"]
        )
        bos = (
            cost_dict["development_cost_modeled"]
            + cost_dict["eng_and_mgmt_cost_modeled"]
            + cost_dict["plant_commissioning_cost_modeled"]
            + cost_dict["site_access_port_staging_cost_modeled"]
            + cost_dict["assembly_and_install_cost_modeled"]
            + cost_dict["other_infrastructure_cost_modeled"]
        )
        elec_infrastruc_costs = (
            cost_dict["array_cable_system_cost_modeled"]
            + cost_dict["export_cable_system_cost_modeled"]
            + cost_dict["onshore_substation_cost_modeled"]
            + cost_dict["offshore_substation_cost_modeled"]
            + cost_dict["other_elec_infra_cost_modeled"]
        )
        financial = (
            cost_dict["project_contingency"]
            + cost_dict["insurance_during_construction"]
            + cost_dict["reserve_accounts"]
        )

        total_installed_cost = capex + bos + elec_infrastruc_costs + financial

        outputs["CapEx"] = total_installed_cost

        opex = cost_dict["maintenance_cost"] + cost_dict["operations_cost"]

        outputs["OpEx"] = opex
