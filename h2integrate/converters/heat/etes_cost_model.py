"""
Cost model for the Electric Thermal Energy Storage (ETES).

Implements the linearized cost functions from the MILP ETES Optimization
Formulation (Lidor, 2026):

    C_TES_total = max(C_lin_TES * S_TES + C_const_TES,  C_min_TES * S_TES)
    C_ch_total  = C_lin_ch * S_ch + C_const_ch     (P-ETES only)
    C_dis_total = C_lin_dis * S_dis + C_const_dis  (P-ETES only)

For R-ETES systems the charging/discharging components are integrated with
storage and S_ch / S_dis cost terms are not used (set their linear/constant
coefficients to zero or leave at default).

OpEx is taken as a fixed fraction of CapEx per the same convention as
``shell_tube_hx_cost_model.py``.
"""

from attrs import field, define

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.core.validators import gt_zero, gte_zero
from h2integrate.core.model_baseclasses import CostModelBaseClass, CostModelBaseConfig


@define(kw_only=True)
class ETESCostModelConfig(CostModelBaseConfig):
    """
    Configuration class for the ETESCostModel.

    Args:
        C_lin_TES (float): ETES storage linear cost coefficient ($/kWh_th).
        C_const_TES (float): ETES storage constant cost term ($).
        C_min_TES (float): Minimum allowed storage cost per kWh_th
            ($/kWh_th). Acts as a lower bound on (C_lin_TES * S_TES +
            C_const_TES) / S_TES.
        C_lin_ch (float): Charging unit linear cost coefficient ($/kW_e).
            Used for P-ETES only.
        C_const_ch (float): Charging unit constant cost term ($).
        C_lin_dis (float): Discharging unit linear cost coefficient
            ($/kW_th). Used for P-ETES only.
        C_const_dis (float): Discharging unit constant cost term ($).
        opex_fraction (float): Annual OpEx as a fraction of total CapEx.
    """

    C_lin_TES: float = field(validator=gte_zero)
    C_const_TES: float = field(default=0.0, validator=gte_zero)
    C_min_TES: float = field(default=0.0, validator=gte_zero)
    C_lin_ch: float = field(default=0.0, validator=gte_zero)
    C_const_ch: float = field(default=0.0, validator=gte_zero)
    C_lin_dis: float = field(default=0.0, validator=gte_zero)
    C_const_dis: float = field(default=0.0, validator=gte_zero)
    opex_fraction: float = field(default=0.04, validator=gte_zero)


class ETESCostModel(CostModelBaseClass):
    """
    Linearized ETES cost model.

    Inputs:
        S_TES_kWh: Storage capacity (kWh_th).
        S_ch_kW: Charging unit electric power rating (kW_e). Used for
            P-ETES; set to 0 for R-ETES.
        S_dis_kW: Discharging unit thermal power rating (kW_th). Used for
            P-ETES; set to 0 for R-ETES.

    Outputs:
        CapEx: Total capital expenditure (USD).
        OpEx: Annual operating expenditure (USD/year).
    """

    def setup(self):
        self.config = ETESCostModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "cost"),
            additional_cls_name=self.__class__.__name__,
        )
        super().setup()

        self.add_input("S_TES_kWh", val=0.0, units="kW*h", desc="Storage capacity")
        self.add_input(
            "S_ch_kW", val=0.0, units="kW", desc="Charging unit electric power rating"
        )
        self.add_input(
            "S_dis_kW", val=0.0, units="kW", desc="Discharging unit thermal power rating"
        )

        self.add_input(
            "C_lin_TES",
            val=self.config.C_lin_TES,
            units="USD/(kW*h)",
            desc="Storage linear cost coefficient",
        )
        self.add_input(
            "C_const_TES",
            val=self.config.C_const_TES,
            units="USD",
            desc="Storage constant cost term",
        )
        self.add_input(
            "C_min_TES",
            val=self.config.C_min_TES,
            units="USD/(kW*h)",
            desc="Minimum storage cost per kWh_th",
        )
        self.add_input(
            "C_lin_ch",
            val=self.config.C_lin_ch,
            units="USD/kW",
            desc="Charging unit linear cost coefficient",
        )
        self.add_input(
            "C_const_ch",
            val=self.config.C_const_ch,
            units="USD",
            desc="Charging unit constant cost term",
        )
        self.add_input(
            "C_lin_dis",
            val=self.config.C_lin_dis,
            units="USD/kW",
            desc="Discharging unit linear cost coefficient",
        )
        self.add_input(
            "C_const_dis",
            val=self.config.C_const_dis,
            units="USD",
            desc="Discharging unit constant cost term",
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        S_TES = float(inputs["S_TES_kWh"][0])
        S_ch = float(inputs["S_ch_kW"][0])
        S_dis = float(inputs["S_dis_kW"][0])

        C_lin_TES = float(inputs["C_lin_TES"][0])
        C_const_TES = float(inputs["C_const_TES"][0])
        C_min_TES = float(inputs["C_min_TES"][0])
        C_lin_ch = float(inputs["C_lin_ch"][0])
        C_const_ch = float(inputs["C_const_ch"][0])
        C_lin_dis = float(inputs["C_lin_dis"][0])
        C_const_dis = float(inputs["C_const_dis"][0])

        # Linearized storage cost with floor (from the MILP formulation:
        # C_TES_total - C_min_TES * S_TES + C_const_TES >= 0  =>
        # C_TES_total >= C_min_TES * S_TES - C_const_TES)
        c_tes_linear = C_lin_TES * S_TES + C_const_TES
        c_tes_floor = C_min_TES * S_TES
        c_tes = max(c_tes_linear, c_tes_floor)

        c_ch = C_lin_ch * S_ch + (C_const_ch if S_ch > 0 else 0.0)
        c_dis = C_lin_dis * S_dis + (C_const_dis if S_dis > 0 else 0.0)

        capex = c_tes + c_ch + c_dis
        opex = self.config.opex_fraction * capex

        outputs["CapEx"] = capex
        outputs["OpEx"] = opex
