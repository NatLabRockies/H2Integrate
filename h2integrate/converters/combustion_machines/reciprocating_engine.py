import numpy as np
import pyfluids
import matplotlib.pyplot as plt
from scipy.optimize import brentq

from h2integrate.converters.combustion_machines.thermo_tools import (
    ThermodynamicCycleResult,
    enforce_gas_phase,
    compute_heat_transfer,
    compute_work_rate_isentropic,
    compute_isentropic_expansion_outlet_state,
    compute_isentropic_compression_outlet_state,
)


def compute_work_rate_compression(
    state_inlet,
    state_outlet,
    mass_flow_fluid=1.0,
    isentropic_efficiency=1.0,
):
    work_rate_isentropic = compute_work_rate_isentropic(
        state_inlet,
        state_outlet,
        mass_flow_fluid=mass_flow_fluid,
    )
    return 1.0 / isentropic_efficiency * work_rate_isentropic  # kW = kJ/s


def compute_work_rate_expansion(
    state_inlet,
    state_outlet,
    mass_flow_fluid=1.0,
    isentropic_efficiency=1.0,
):
    work_rate_isentropic = compute_work_rate_isentropic(
        state_inlet,
        state_outlet,
        mass_flow_fluid=mass_flow_fluid,
    )
    return isentropic_efficiency * work_rate_isentropic  # kW = kJ/s


class RICE:
    """
    Reciprocal Internal Combustion Engine (RICE) thermodynamic cycle model.

    Simulates an Otto cycle engine with configurable compression and expansion
    stroke isentropic efficiencies. Computes work outputs, heat transfers, and
    thermodynamic states throughout the engine cycle given ambient conditions.
    """

    no_stroke: int = 4  # -, 2-stroke or 4-stroke engine
    ratio_compression: float  # -, compression ratio
    Trel_combustion: float  # deg C, relative temperature
    isentropic_efficiency_compression: float  # -, compression stroke isentropic efficiency
    isentropic_efficiency_expansion: float  # -, expansion stroke isentropic efficiency
    displacement_engine: float  # m**3, engine displacement
    rpm_operating: float  # rev/min, engine RPM

    design_conditions: dict  # design conditions dictionary

    def __init__(
        self,
        ratio_compression: float,  # -, compression ratio
        Trel_combustion: float,  # deg C, relative temperature
        isentropic_efficiency_compression: float,  # -, compression stroke isentropic efficiency
        isentropic_efficiency_expansion: float,  # -, expansion stroke isentropic efficiency
        displacement_engine: (
            float | None
        ) = None,  # m**3, engine displacement; unit-mass analysis if None
        rpm_operating: (float | None) = None,  # rev/min, engine RPM; unit-mass analysis if None
        design_conditions=None,  # dict, design conditions dictionary
    ):
        # set in variables
        self.ratio_compression = ratio_compression
        self.Trel_combustion = Trel_combustion
        self.isentropic_efficiency_compression = isentropic_efficiency_compression
        self.isentropic_efficiency_expansion = isentropic_efficiency_expansion
        self.displacement_engine = displacement_engine
        self.rpm_operating = rpm_operating

        if design_conditions is not None:
            self.design_conditions = design_conditions

    def get_revs_per_cycle(self):
        # mechanical cycles per thermodynamic cycle
        return self.no_stroke / 2  # -

    def get_mean_effective_pressure(
        self,
        power_setpoint,  # kW, indicated power at which to evaluate
        rpm_setpoint,  # rev/min., RPM at which to evaluate
    ):
        mep = (
            power_setpoint
            / self.displacement_engine
            / (
                rpm_setpoint / 60.0 / self.get_revs_per_cycle()  # to thermodynamic cycle Hz
            )
            * 1.0e3
        )  # Pa
        return mep  # Pa

    def invert_mean_effective_pressure(
        self,
        mean_effective_pressure_value,  # Pa, MEP at which to evaluate
        rpm_setpoint,  # rev/min., RPM at which to evaluate
    ):
        power = (
            self.displacement_engine
            * (
                mean_effective_pressure_value / 1.0e3  # convert to kPa
            )
            * (
                rpm_setpoint / 60.0 / self.get_revs_per_cycle()  # to thermodynamic cycle Hz
            )
        )  # kW
        return power  # kW

    def run_engine_model(
        self,
        fluid_ambient_list: (
            list[pyfluids.fluids.abstract_fluid.AbstractFluid]
            | pyfluids.fluids.abstract_fluid.AbstractFluid
        ),
        rpm_setpoint_list: list[float] | float | None = None,
    ):
        singleton = False  # make a flag if there's just one state to run
        singleton_ambient = False  # make a flag if there's just one state to run
        singleton_rpm = False  # make a flag if there's just one state to run

        if isinstance(
            fluid_ambient_list,
            pyfluids.fluids.abstract_fluid.AbstractFluid,
        ):
            fluid_ambient_list = [
                fluid_ambient_list,
            ]
            singleton_ambient = True

        if isinstance(
            rpm_setpoint_list,
            float,
        ):
            rpm_setpoint_list = [
                rpm_setpoint_list,
            ]
            singleton_rpm = True

        if singleton_ambient and singleton_rpm:
            singleton = True
        elif singleton_ambient:
            fluid_ambient_list = [fluid_ambient_list[0] for _ in len(rpm_setpoint_list)]
        elif singleton_rpm:
            rpm_setpoint_list = [rpm_setpoint_list[0] for _ in len(fluid_ambient_list)]

        assert (rpm_setpoint_list is None) or (len(rpm_setpoint_list) == len(fluid_ambient_list))

        results = []  # vector to store results for each ambient fluid state
        for fluid_ambient, rpm_setpoint in zip(
            fluid_ambient_list, rpm_setpoint_list
        ):  # loop over ambient fluid states
            ### CALCULATE THE CYCLE STATES
            # note: gas phase enforcement speeds up computation significantly

            enforce_gas_phase(fluid_ambient)  # ensure the ambient fluid is in the gas phase
            fluid_compressed = compute_isentropic_compression_outlet_state(
                fluid_ambient,
                ratio_compression=self.ratio_compression,
            )  # after compression stroke
            enforce_gas_phase(fluid_compressed)  # ensure the compressed fluid is in the gas phase
            fluid_combusted = fluid_compressed.with_state(
                pyfluids.Input.specific_volume(fluid_compressed.specific_volume),
                pyfluids.Input.temperature(self.Trel_combustion),
            )  # after the combustion
            enforce_gas_phase(fluid_combusted)  # ensure the combusted fluid is in the gas phase
            fluid_exhaust = compute_isentropic_expansion_outlet_state(
                fluid_combusted,
                ratio_compression=self.ratio_compression,
            )  # exhaust from the combustion process
            enforce_gas_phase(fluid_exhaust)  # ensure the exhaust fluid is in the gas phase

            ### CALCULATE THE WORK INPUTS/OUTPUTS
            wdot_compression_stroke = compute_work_rate_compression(
                fluid_ambient,
                fluid_compressed,
                isentropic_efficiency=self.isentropic_efficiency_compression,
            )  # now that the gas states are determined, compute the work
            wdot_expansion_stroke = compute_work_rate_expansion(
                fluid_combusted,
                fluid_exhaust,
                isentropic_efficiency=self.isentropic_efficiency_expansion,
            )  # now that the gas states are determined, compute the work

            mep_total_friction = self.compute_tfmep_model(rpm_setpoint)

            ### CALCULATE THE HEAT INPUTS/OUTPUTS
            qdot_combustion = compute_heat_transfer(
                fluid_compressed,
                fluid_combusted,
            )  # now that the gas states are determined, compute the heat transfer
            qdot_rejection = compute_heat_transfer(
                fluid_exhaust,
                fluid_ambient,
            )  # now that the gas states are determined, compute the heat transfer

            ### CALCULATE THE MASS FLOWRATE W/ CONTROL IF APPLICABLE
            mass_flowrate = self.get_mass_flowrate(fluid_ambient, rpm_setpoint)

            ### PACK THE RESULT
            result = ThermodynamicCycleResult(
                "Otto cycle engine",
                closed=True,
            )

            # add mass flowrate
            result.mass_flowrate = mass_flowrate

            # add states
            result.add_state(1, fluid_ambient, "ambient intake air")
            result.add_state(2, fluid_compressed, "compressed at TDC")
            result.add_state(3, fluid_combusted, "after combustion at TDC")
            result.add_state(4, fluid_exhaust, "exhaust at BDC")

            # add processes
            result.add_process(
                1,
                2,
                wdot_compression_stroke,
                0.0,
                "compression stroke",
            )
            result.add_process(
                2,
                3,
                0.0,
                qdot_combustion,
                "combustion at TDC",
            )
            result.add_process(
                3,
                4,
                wdot_expansion_stroke,
                0.0,
                "expansion stroke",
            )
            result.add_process(
                4,
                1,
                0.0,
                qdot_rejection,
                "exhaust heat rejection",
            )

            result.add_loss(
                1,
                self.invert_mean_effective_pressure(
                    mep_total_friction,
                    rpm_setpoint,
                )
                / self.get_mass_flowrate(fluid_ambient, rpm_setpoint),
                "total friction loss",
            )

            # return logic
            if singleton:
                return result
            results.append(result)

        return results

    def get_volumetric_flowrate_engine(
        self,
        rpm_setpoint=None,  # revs/min, crankshaft RPM
    ) -> float:
        if rpm_setpoint is None:
            rpm_setpoint = self.rpm_operating
        # note: 4-cycle have 2 mech. cycles per thermo. cycle
        return self.displacement_engine * (
            rpm_setpoint / 60.0 / self.get_revs_per_cycle()
        )  # m**3/s

    def get_mass_flowrate(
        self,
        fluid_intake_manifold: pyfluids.fluids.abstract_fluid.AbstractFluid,
        rpm_setpoint=None,  # revs/min, crankshaft RPM
    ) -> float:
        Q_flow = self.get_volumetric_flowrate_engine(rpm_setpoint=rpm_setpoint)
        return fluid_intake_manifold.density * Q_flow

    @staticmethod
    def compute_tfmep_model(rpm_in: np.ndarray | float) -> np.ndarray | float:
        return (
            0.97 + 0.15 * rpm_in / 1000.0 + 0.05 * (rpm_in / 1000.0) ** 2
        ) * 100.0e3  # SI model from S13.5.1 of Heywood, _Internal Combustion Engine Fundamentals_


if __name__ == "__main__":
    # options
    do_optimization = False
    engine_name = "LS1"

    if engine_name == "LS1":
        # ambient air conditions
        P_ambient = 101325.0  # Pa, ISO conditions
        Trel_ambient = 17.0  # °C, ISO conditions
        rel_humidity_ambient = 60  # %, ISO conditions

        # engine design settings
        ratio_compression = 10.1  # -, engine compression ratio LS-1
        Trel_combustion = 2126.5607669775  # °C, reverse engineered to achieve max power curve HP
        isentropic_efficiency_compression = 1.0  # -, textbook assumption
        isentropic_efficiency_expansion = 1.0  # -, textbook assumption
        displacement_engine = 5.7e-3  # m**3, engine displacement LS-1
        rpm_operating = 5600.0  # revs/min, "typical redline"
        P_rated = 257.27  # kW, C5 Corvette w/ LS-1
    else:
        # ambient air conditions
        P_ambient = 100000.0  # Pa, from Cengel ex. 9-3
        Trel_ambient = 17.0  # °C, from Cengel ex. 9-3
        rel_humidity_ambient = 60

        # engine thermodynamic design settings
        ratio_compression = 8.0  # -, engine compression ratio from Cengel ex. 9-3
        Trel_combustion = (
            1575.1 - 273.15
        )  # °C, engine maximum temperature of combustion from Cengel ex. 9-3

    if do_optimization:
        # use Brent's method to find Trel_combustion that achieves expected power
        def power_error(Trel_comb):
            """Calculate power error from expected rated power."""
            ice = RICE(
                ratio_compression=ratio_compression,
                Trel_combustion=Trel_comb,
                isentropic_efficiency_compression=isentropic_efficiency_compression,
                isentropic_efficiency_expansion=isentropic_efficiency_expansion,
                displacement_engine=displacement_engine,
                rpm_operating=rpm_operating,
            )
            working_fluid = pyfluids.Fluid(pyfluids.FluidsList.Air)
            fluid_ambient = working_fluid.with_state(
                pyfluids.Input.pressure(P_ambient),
                pyfluids.Input.temperature(Trel_ambient),
            )
            result = ice.run_engine_model(fluid_ambient, ice.rpm_operating)
            net_power = result.get_net_work(losses=True)
            return net_power - P_rated

        # Find Trel_combustion using Brent's method
        Trel_combustion_optimal = brentq(power_error, 800, 2500)

        print(f"Optimal Trel_combustion: {Trel_combustion_optimal:.10f} °C")
        print(f"Expected power: {P_rated:.2f} kW")

    elif True:
        ice = RICE(
            ratio_compression=ratio_compression,
            Trel_combustion=Trel_combustion,
            isentropic_efficiency_compression=isentropic_efficiency_compression,
            isentropic_efficiency_expansion=isentropic_efficiency_expansion,
            displacement_engine=displacement_engine,
            rpm_operating=rpm_operating,
        )

        # start with ISO conditions
        working_fluid = pyfluids.Fluid(pyfluids.FluidsList.Air)
        # working_fluid = make_humid_air_mixture(
        #     P_ambient,
        #     Trel_ambient,
        #     rel_humidity_ambient,
        # )

        # create the ambient pyfluid fluid
        fluid_ambient = working_fluid.with_state(
            pyfluids.Input.pressure(P_ambient),
            pyfluids.Input.temperature(Trel_ambient),
        )

        # run the engine model
        result = ice.run_engine_model(fluid_ambient, ice.rpm_operating)
        result.mass_flowrate = ice.get_mass_flowrate(fluid_ambient, ice.rpm_operating)
        vfr = ice.get_volumetric_flowrate_engine(ice.rpm_operating)

        # print the output
        print(result)
        print("totals:")
        print(f"\tnet power: {result.get_net_work():.02f} kW")
        print(f"\tefficiency: {result.get_efficiency():.03f}%")
        print(
            f"\tnet heat: {result.get_net_heat_input() + result.get_net_heat_rejection():.02f} kW"
        )
        print(f"volumetric flowrate: {vfr:.03f} m**3/s")
        print(f"mass flowrate: {ice.get_mass_flowrate(fluid_ambient, ice.rpm_operating):.03f} kg/s")
        print(f"net power: {result.get_net_work():.02f} kW")

        rpm_vec = np.linspace(1000.0, 6000.0, 201)
        mass_flowrate_vec = [ice.get_mass_flowrate(fluid_ambient, rpm_val) for rpm_val in rpm_vec]
        power_vec = [ice.get_mass_flowrate(fluid_ambient, rpm_val) for rpm_val in rpm_vec]
        result.mass_flowrate = None
        plt.plot(rpm_vec, mass_flowrate_vec)
        plt.show()

    else:
        ice = RICE(
            ratio_compression=ratio_compression,
            Trel_combustion=Trel_combustion,
            isentropic_efficiency_compression=isentropic_efficiency_compression,
            isentropic_efficiency_expansion=isentropic_efficiency_expansion,
            displacement_engine=displacement_engine,
            rpm_operating=rpm_operating,
        )

        # start with ISO conditions
        working_fluid = pyfluids.Fluid(pyfluids.FluidsList.Air)
        # working_fluid = make_humid_air_mixture(
        #     P_ambient,
        #     Trel_ambient,
        #     rel_humidity_ambient,
        # )

        # create the ambient pyfluid fluid
        P_vec = P_ambient * np.linspace(0.75, 1.0, 201)
        fluids_ambient = [
            working_fluid.with_state(
                pyfluids.Input.pressure(P_current),
                pyfluids.Input.temperature(Trel_ambient),
            )
            for P_current in P_vec
        ]

        # run the engine model
        results = ice.run_engine_model(fluids_ambient)
        for f, r in zip(fluids_ambient, results):
            r.mass_flowrate = ice.get_mass_flowrate(f)
        efficiency_vec = np.array([r.get_efficiency() for r in results])
        net_power_vec = np.array([r.get_net_work() for r in results])

        fig, axes = plt.subplots(2, 1, sharex=True)
        axes[0].plot(P_vec, net_power_vec / P_rated)
        axes[1].plot(P_vec, efficiency_vec)

        plt.show()

        print(results[-1])

        print(f"net work: {results[-1].get_net_work(losses=False):.02f}")
        print(f"net work before losses: {results[-1].get_net_work(losses=True):.02f}")
        print(f"{ice.get_mean_effective_pressure(results[-1].get_net_work()):.02f}")
