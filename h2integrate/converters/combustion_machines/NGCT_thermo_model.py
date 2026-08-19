import numpy as np
import pyfluids

from h2integrate.converters.combustion_machines.thermo_tools import (
    ThermodynamicCycleResult,
    enforce_gas_phase,
    compute_heat_transfer,
    compute_turbine_work_rate,
    compute_compressor_work_rate,
    compute_isentropic_expansion_outlet_state,
    compute_isentropic_compression_outlet_state,
)


class NGCT:
    """
    Thermodynamic model for the performance of a natural gas combustion turbine.

    Thermodynamic model for the performance of a specific natural gas combustion
    turbine. We assume a Brayton cycle with isentropic efficiency corrections
    for the compressor and turbine work. The turbine is assumed to ingest the
    intake fluid at maximum a specific volumetric flowrate. We also assume that
    the combustion chamber and turbine set the maximum designed firing
    temperature.
    """

    ratio_P: float  # -, pressure ratio
    Trel_firing: float  # deg C, relative temperature
    isentropic_efficiency_compressor: float  # -, compressor isentropic efficiency
    isentropic_efficiency_turbine: float  # -, turbine isentropic efficiency
    Q_fluid_max: float  # m**3/s, design volumetric flowrate

    def __init__(
        self,
        ratio_P: float,  # -, pressure ratio
        Trel_firing: float,  # deg C, relative temperature
        isentropic_efficiency_compressor: float,  # -, compressor isentropic efficiency
        isentropic_efficiency_turbine: float,  # -, turbine isentropic efficiency
        Q_fluid_max: (
            float | None
        ) = None,  # m**3/s, design volumetric flowrate; unit-mass analysis if None
    ):
        # set in variables
        self.ratio_P = ratio_P
        self.Trel_firing = Trel_firing
        self.isentropic_efficiency_compressor = isentropic_efficiency_compressor
        self.isentropic_efficiency_turbine = isentropic_efficiency_turbine
        self.Q_fluid_max = Q_fluid_max

    def run_turbine_model(
        self,
        fluid_ambient_list: list[pyfluids.fluids.abstract_fluid.AbstractFluid],
        power_rated: float = np.inf,  # kW, maximum rated power of the system
        heatrate_fuel_capacity: float = np.inf,  # kJ/s, maximum allowable heat rate
    ) -> list[ThermodynamicCycleResult]:
        """
        Run the Brayton cycle model for a list of ambient fluid states.

        For each ambient fluid state, the cycle states are computed through the
        compressor, combustor, and turbine, then the specific work and heat
        terms are evaluated. If a design volumetric flowrate is set, the mass
        flowrate is also computed subject to the volumetric, power rating, and
        fuel heat rate limits.

        Args:
            fluid_ambient_list: Ambient fluid states to evaluate, one per
                operating condition. A single condition should be passed as a
                list of length one.
            power_rated: Generator power rating constraint (kW). Defaults to no
                limit.
            heatrate_fuel_capacity: Fuel heat rate capacity limit (kJ/s).
                Defaults to no limit.

        Returns:
            One ThermodynamicCycleResult per entry in fluid_ambient_list, in the
            same order.
        """
        results = []  # vector to store results for each ambient fluid state
        for fluid_ambient in fluid_ambient_list:  # loop over ambient fluid states
            ### CALCULATE THE CYCLE STATES
            # note: gas phase enforcement speeds up computation significantly

            enforce_gas_phase(fluid_ambient)  # ensure the ambient fluid is in the gas phase
            fluid_compressed = compute_isentropic_compression_outlet_state(
                fluid_ambient,
                ratio_P=self.ratio_P,
            )  # after the compressor
            enforce_gas_phase(fluid_compressed)  # ensure the compressed fluid is in the gas phase
            fluid_combusted = fluid_compressed.with_state(
                pyfluids.Input.pressure(fluid_compressed.pressure),
                pyfluids.Input.temperature(self.Trel_firing),
            )  # after the combustion chamber
            enforce_gas_phase(fluid_combusted)  # ensure the combusted fluid is in the gas phase
            fluid_exhaust = compute_isentropic_expansion_outlet_state(
                fluid_combusted,
                ratio_P=self.ratio_P,
            )  # exhaust from the turbine
            enforce_gas_phase(fluid_exhaust)  # ensure the exhaust fluid is in the gas phase

            ### CALCULATE THE WORK INPUTS/OUTPUTS
            wdot_compressor = compute_compressor_work_rate(
                fluid_ambient,
                fluid_compressed,
                isentropic_efficiency=self.isentropic_efficiency_compressor,
            )  # now that the gas states are determined, compute the work
            wdot_turbine = compute_turbine_work_rate(
                fluid_combusted,
                fluid_exhaust,
                isentropic_efficiency=self.isentropic_efficiency_turbine,
            )  # now that the gas states are determined, compute the work

            ### CALCULATE THE HEAT INPUTS/OUTPUTS
            qdot_HX_combustor = compute_heat_transfer(
                fluid_compressed,
                fluid_combusted,
            )  # now that the gas states are determined, compute the heat transfer
            qdot_HX_exhaust_rejection = compute_heat_transfer(
                fluid_exhaust,
                fluid_ambient,
            )  # now that the gas states are determined, compute the heat transfer

            ### CALCULATE THE MASS FLOWRATE W/ CONTROL IF APPLICABLE
            mass_flowrate = (
                NGCT.get_mass_flowrate(
                    fluid_ambient,
                    self.Q_fluid_max,
                    wdot_turbine,
                    wdot_compressor,
                    qdot_HX_combustor,
                    power_rated=power_rated,
                    heatrate_fuel_capacity=heatrate_fuel_capacity,
                )
                if self.Q_fluid_max is not None
                else None
            )  # use static method

            ### PACK THE RESULT
            result = ThermodynamicCycleResult(
                "Brayton cycle combustion turbine",
                closed=True,
            )

            # add mass flowrate
            result.mass_flowrate = mass_flowrate

            # add states
            result.add_state(1, fluid_ambient, "ambient intake air")
            result.add_state(2, fluid_compressed, "compressed air")
            result.add_state(3, fluid_combusted, "products of combustion")
            result.add_state(4, fluid_exhaust, "exhaust air")

            # add processes
            result.add_process(
                1,
                2,
                wdot_compressor,
                0.0,
                "isentropic compressor w/ work efficiency correction",
            )
            result.add_process(
                2,
                3,
                0.0,
                qdot_HX_combustor,
                "constant-pressure heating",
            )
            result.add_process(
                3,
                4,
                wdot_turbine,
                0.0,
                "isentropic turbine w/ work efficiency correction",
            )
            result.add_process(
                4,
                1,
                0.0,
                qdot_HX_exhaust_rejection,
                "constant-pressure (atmospheric) cooling",
            )

            results.append(result)

        return results

    @staticmethod
    def get_mass_flowrate(
        fluid_ambient: pyfluids.fluids.abstract_fluid.AbstractFluid,
        Q_fluid_max: float,
        wdot_turbine: float,
        wdot_compressor: float,
        qdot_HX_combustor: float,
        power_rated: float = np.inf,
        heatrate_fuel_capacity: float = np.inf,
    ) -> float:
        """
        Calculate the mass flowrate constrained by design and operational limits.

        Determines the actual mass flowrate as the minimum of multiple limiting
        cases: volumetric flow capacity, power rating, and heat rate capacity.

        Args:
            fluid_ambient: Ambient fluid mixture with density property
                (pyfluids.fluids.abstract_fluid.AbstractFluid)
            Q_fluid_max: Maximum volumetric flowrate design limit (m**3/s)
            wdot_turbine: Turbine work output (kW/kg)
            wdot_compressor: Compressor work input (kW/kg)
            qdot_HX_combustor: Heat released by combustor (kW/kg)
            power_rated: Generator power rating constraint (kW), optional
            heatrate_fuel_capacity: Fuel heat capacity flow limit (kJ/s), optional

        Returns:
            Mass flowrate (kg/s) limited by the most restrictive constraint
        """
        # maximum mass flowrate allowed by the design
        mass_flowrate_max = fluid_ambient.density * Q_fluid_max  # kg/s
        # make a list of potential limiting cases
        mass_flowrate_candidates = [mass_flowrate_max]

        # throttle air/fuel flow to stay under given power rating (i.e. generator)
        mass_flowrate_candidates.append(
            power_rated / (wdot_turbine + wdot_compressor)  # kg/s <= [kW = kJ/s]/[kJ/kg]
        )

        # if flowrate is limited by a MMBtu/s (or kJ/s) flow limit
        mass_flowrate_candidates.append(
            heatrate_fuel_capacity / qdot_HX_combustor  # kg/s <= [kJ/s] / [kJ/kg]
        )

        # the actual mass flowrate is the minimum of the limiting cases
        return float(np.min(mass_flowrate_candidates))
