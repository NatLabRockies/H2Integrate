import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig, merge_shared_inputs
from h2integrate.core.validators import gt_zero
from h2integrate.converters.heat.heat_exchanger_model.hx_shell_tube_steady import (
    hx_shell_tube_steady,
)


@define()
class ShellTubeHXPerformanceModelConfig(BaseConfig):
    """
    Configuration class for the ShellTubeHXPerformanceModel.

    Args:
        Th_in_C (float): Hot fluid inlet temperature in degrees Celsius.
        Tc_in_C (float): Cold fluid inlet temperature in degrees Celsius.
        m_dot_h_kg_s (float): Mass flow rate of the hot fluid in kg/s.
        m_dot_c_kg_s (float): Mass flow rate of the cold fluid in kg/s.
        N_tubes (int): Number of tubes in the heat exchanger.
        N_passes (int): Number of passes in the heat exchanger.
        L_tube_m (float): Length of each tube in meters.
        D_o_m (float): Outer diameter of the tubes in meters.
        t_wall_m (float): Wall thickness of the tubes in meters.
        D_shell_m (float): Diameter of the shell in meters.
        cost_year (int): Year for cost estimation.
    """

    Th_in_C: float = field(validator=gt_zero)
    Tc_in_C: float = field(validator=gt_zero)
    m_dot_h_kg_s: float = field(validator=gt_zero)
    m_dot_c_kg_s: float = field(validator=gt_zero)
    N_tubes: int = field(validator=gt_zero)
    N_passes: int = field(validator=gt_zero)
    L_tube_m: float = field(validator=gt_zero)
    D_o_m: float = field(validator=gt_zero)
    t_wall_m: float = field(validator=gt_zero)
    D_shell_m: float = field(validator=gt_zero)
    cost_year: int = field(validator=gt_zero)


class ShellTubeHXPerformanceModel(om.ExplicitComponent):
    """
    An OpenMDAO component that wraps the steady shell tube heat exchanger model.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        # Load in user config from input file
        self.config = ShellTubeHXPerformanceModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance"),
        )

        # Setup OpenMDAO inputs
        self.add_input(
            "Th_in_C", val=self.config.Th_in_C, units="C", desc="Hot fluid inlet temperature"
        )
        self.add_input(
            "Tc_in_C", val=self.config.Tc_in_C, units="C", desc="Cold fluid inlet temperature"
        )
        self.add_input(
            "m_dot_h_kg_s",
            val=self.config.m_dot_h_kg_s,
            units="kg/s",
            desc="Hot fluid mass flow rate",
        )
        self.add_input(
            "m_dot_c_kg_s",
            val=self.config.m_dot_c_kg_s,
            units="kg/s",
            desc="Cold fluid mass flow rate",
        )

        # Setup OpenMDAO outputs
        self.add_output("Th_out_C", val=0.0, units="C", desc="Hot fluid outlet temperature")
        self.add_output("Tc_out_C", val=0.0, units="C", desc="Cold fluid outlet temperature")
        self.add_output("Q_total_kW", val=0.0, units="kW", desc="Total heat transfer rate")
        self.add_output("epsilon", val=0.0, desc="Effectiveness of the heat exchanger")
        self.add_output("NTU", val=0.0, desc="Number of transfer units")
        self.add_output("C_r", val=0.0, desc="Heat capacity rate ratio")
        self.add_output(
            "U_global_W_m2K", val=0.0, units="W/m**2/K", desc="Overall heat transfer coefficient"
        )
        self.add_output("dp_hot_Pa", val=0.0, units="Pa", desc="Pressure drop on the hot side")
        self.add_output("dp_cold_Pa", val=0.0, units="Pa", desc="Pressure drop on the cold side")
        self.add_output("pump_power_kW", val=0.0, units="kW", desc="Total pump power required")
        self.add_output("S_gen_dot_W_per_K", val=0.0, units="W/K", desc="Entropy generation rate")
        self.add_output("Ex_dest_dot_kW", val=0.0, units="kW", desc="Exergy destruction rate")

    def compute(self, inputs, outputs):
        params = {
            "Th_in": inputs["Th_in_C"],
            "Tc_in": inputs["Tc_in_C"],
            "m_dot_h": inputs["m_dot_h_kg_s"],
            "m_dot_c": inputs["m_dot_c_kg_s"],
            "N_tubes": self.config.N_tubes,
            "N_passes": self.config.N_passes,
            "L_tube": self.config.L_tube_m,
            "D_o": self.config.D_o_m,
            "t_wall": self.config.t_wall_m,
            "D_shell": self.config.D_shell_m,
        }

        res = hx_shell_tube_steady(params)

        outputs["Th_out_C"] = float(res["Th"][-1])
        outputs["Tc_out_C"] = float(res["Tc"][0])
        outputs["Q_total_kW"] = float(res["Q_total"]) / 1e3
        outputs["epsilon"] = float(res["epsilon"])
        outputs["NTU"] = float(res["NTU"])
        outputs["C_r"] = float(res["C_r"])
        outputs["U_global_W_m2K"] = float(res["U_global"])
        outputs["dp_hot_Pa"] = float(res["dp_tube_total"])
        outputs["dp_cold_Pa"] = float(res["dp_shell_total"])
        outputs["pump_power_kW"] = float(res["P_pump_total"]) / 1e3
        outputs["S_gen_dot_W_per_K"] = float(res["S_gen_dot"])
        outputs["Ex_dest_dot_kW"] = float(res["Ex_dest_dot"]) / 1e3
