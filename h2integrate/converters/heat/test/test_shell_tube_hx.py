import copy

import numpy as np
import pytest
import openmdao.api as om
from pytest import approx, fixture

from h2integrate.converters.heat.shell_tube_hx_performance_model import ShellTubeHXPerformanceModel


@fixture
def shell_tube_hx_config():
    performance_parameters = {
        "process_fluid_temp_C": 90.0,
        "working_fluid_temp_C": 30.0,
        "process_fluid_mass_flow_kg_s": 18.0,
        "working_fluid_mass_flow_kg_s": 40.0,
        "process_fluid_pressure_bar": 1.0,
        "working_fluid_pressure_bar": 1.0,
        "N_tubes": 192,
        "N_passes": 2,
        "L_tube_m": 4.9,
        "D_o_m": 0.01905,
        "t_wall_m": 0.002,
        "D_shell_m": 0.591,
    }

    tech_config = {
        "model_inputs": {
            "performance_parameters": performance_parameters,
        }
    }
    plant_config = {
        "plant": {
            "simulation": {"n_timesteps": 1, "dt": 3600},
            "plant_life": 30,
        }
    }
    driver_config: dict = {}
    return tech_config, plant_config, driver_config


@pytest.mark.unit
class TestShellTubeHXPerformanceModel:
    def _create_problem(self, config, n_timesteps=None, **performance_overrides):
        tech_config, plant_config, driver_config = copy.deepcopy(config)
        if n_timesteps is not None:
            plant_config["plant"]["simulation"]["n_timesteps"] = n_timesteps
        tech_config["model_inputs"]["performance_parameters"].update(performance_overrides)
        prob = om.Problem()
        prob.model.add_subsystem(
            "shell_tube_hx",
            ShellTubeHXPerformanceModel(
                tech_config=tech_config,
                plant_config=plant_config,
                driver_config=driver_config,
            ),
            promotes=["*"],
        )
        prob.setup()
        return prob

    def test_hx_performance_calculation(self, shell_tube_hx_config, subtests):
        prob = self._create_problem(shell_tube_hx_config)

        prob.run_model()

        # Multivariable-stream outlet values
        process_temp_out = prob.get_val("shell_tube_hx.process_fluid:temperature_out", units="degC")
        working_temp_out = prob.get_val("shell_tube_hx.working_fluid:temperature_out", units="degC")
        process_mass_flow_out = prob.get_val(
            "shell_tube_hx.process_fluid:mass_flow_out", units="kg/s"
        )
        working_mass_flow_out = prob.get_val(
            "shell_tube_hx.working_fluid:mass_flow_out", units="kg/s"
        )
        process_pressure_out = prob.get_val("shell_tube_hx.process_fluid:pressure_out", units="bar")
        working_pressure_out = prob.get_val("shell_tube_hx.working_fluid:pressure_out", units="bar")

        # Diagnostic scalar-like outputs (time-series of length 1)
        C_r = prob.get_val("shell_tube_hx.heat_capacity_rate_ratio")
        Ex_dest_dot_kW = prob.get_val("shell_tube_hx.exergy_destruction_rate", units="kW")
        NTU = prob.get_val("shell_tube_hx.number_of_transfer_units")
        Q_total_kW = prob.get_val("shell_tube_hx.total_heat_transfer_rate", units="kW")
        S_gen_dot_W_per_K = prob.get_val("shell_tube_hx.entropy_generation_rate", units="W/K")
        U_global_W_m2K = prob.get_val(
            "shell_tube_hx.overall_heat_transfer_coefficient", units="W/m**2/K"
        )
        dp_working_Pa = prob.get_val("shell_tube_hx.pressure_drop_working_fluid", units="Pa")
        dp_process_Pa = prob.get_val("shell_tube_hx.pressure_drop_process_fluid", units="Pa")
        epsilon = prob.get_val("shell_tube_hx.hx_effectiveness")
        pump_power_kW = prob.get_val("shell_tube_hx.pump_power", units="kW")

        # Expected values (regression values captured for this config)
        expected_C_r = 0.4527329816950921
        expected_Ex_dest_dot_kW = 248.78629912498585
        expected_NTU = 0.9142424832326593
        expected_Q_total_kW = 2462.235075109509
        expected_S_gen_dot_W_per_K = 834.433335988549
        expected_working_temp_out_C = 44.72803509154916
        expected_process_temp_out_C = 57.381403669025964
        expected_U_global_W_m2K = 1229.0775390792805
        expected_dp_working_Pa = 201.87162586061777
        expected_dp_process_Pa = 10251.659491792187
        expected_epsilon = 0.5421484468743297
        expected_pump_power_kW = 0.28157427036731625

        rel = 1e-5
        with subtests.test("total_heat_transfer_rate"):
            assert Q_total_kW[0] == approx(expected_Q_total_kW, rel=rel)
        with subtests.test("overall_heat_transfer_coefficient"):
            assert U_global_W_m2K[0] == approx(expected_U_global_W_m2K, rel=rel)
        with subtests.test("heat_capacity_rate_ratio"):
            assert C_r[0] == approx(expected_C_r, rel=rel)
        with subtests.test("exergy_destruction_rate"):
            assert Ex_dest_dot_kW[0] == approx(expected_Ex_dest_dot_kW, rel=rel)
        with subtests.test("number_of_transfer_units"):
            assert NTU[0] == approx(expected_NTU, rel=rel)
        with subtests.test("entropy_generation_rate"):
            assert S_gen_dot_W_per_K[0] == approx(expected_S_gen_dot_W_per_K, rel=rel)
        with subtests.test("working_fluid:temperature_out"):
            assert working_temp_out[0] == approx(expected_working_temp_out_C, rel=rel)
        with subtests.test("process_fluid:temperature_out"):
            assert process_temp_out[0] == approx(expected_process_temp_out_C, rel=rel)
        with subtests.test("pressure_drop_working_fluid"):
            assert dp_working_Pa[0] == approx(expected_dp_working_Pa, rel=rel)
        with subtests.test("pressure_drop_process_fluid"):
            assert dp_process_Pa[0] == approx(expected_dp_process_Pa, rel=rel)
        with subtests.test("hx_effectiveness"):
            assert epsilon[0] == approx(expected_epsilon, rel=rel)
        with subtests.test("pump_power"):
            assert pump_power_kW[0] == approx(expected_pump_power_kW, rel=rel)

        # Mass flow is conserved through the HX
        with subtests.test("process_fluid:mass_flow_out conserved"):
            assert process_mass_flow_out[0] == approx(18.0, rel=1e-12)
        with subtests.test("working_fluid:mass_flow_out conserved"):
            assert working_mass_flow_out[0] == approx(40.0, rel=1e-12)

        # Outlet pressure = inlet pressure - Δp (converted from Pa to bar)
        with subtests.test("process_fluid:pressure_out"):
            assert process_pressure_out[0] == approx(1.0 - expected_dp_process_Pa / 1e5, rel=rel)
        with subtests.test("working_fluid:pressure_out"):
            assert working_pressure_out[0] == approx(1.0 - expected_dp_working_Pa / 1e5, rel=rel)

        with subtests.test("no guardrail flags raised"):
            assert prob.get_val("shell_tube_hx.no_heat_transfer")[0] == 0.0
            assert prob.get_val("shell_tube_hx.solver_warning")[0] == 0.0

    def test_hx_timeseries_shape(self, shell_tube_hx_config, subtests):
        """Confirm the model runs for n_timesteps > 1 and returns time-series outputs."""
        tech_config, plant_config, driver_config = shell_tube_hx_config
        # Bump n_timesteps and rerun
        plant_config = {
            "plant": {
                "simulation": {"n_timesteps": 3, "dt": 3600},
                "plant_life": 30,
            }
        }
        prob = self._create_problem((tech_config, plant_config, driver_config))
        prob.run_model()

        Q = prob.get_val("shell_tube_hx.total_heat_transfer_rate", units="kW")
        with subtests.test("total_heat_transfer_rate shape"):
            assert Q.shape == (3,)
        # All timesteps use the same (config-default) inlets, so results are identical
        with subtests.test("total_heat_transfer_rate constant across timesteps"):
            assert np.allclose(Q, Q[0])

    def test_hx_role_swap(self, shell_tube_hx_config, subtests):
        """Working fluid entering hotter than the process fluid triggers the role swap.

        Timestep 0 uses the nominal inlets (process hot, working cold). Timestep 1 exchanges
        the process and working inlet states, so the working fluid is hotter. Both streams are
        water, so after the internal swap the solver sees identical hot/cold inputs and the
        timestep 1 results should mirror timestep 0 with the stream roles exchanged.
        """
        tech_config, _, driver_config = shell_tube_hx_config
        plant_config = {
            "plant": {
                "simulation": {"n_timesteps": 2, "dt": 3600},
                "plant_life": 30,
            }
        }
        prob = self._create_problem((tech_config, plant_config, driver_config))
        prob.set_val("process_fluid:temperature_in", [90.0, 30.0], units="degC")
        prob.set_val("process_fluid:mass_flow_in", [18.0, 40.0], units="kg/s")
        prob.set_val("working_fluid:temperature_in", [30.0, 90.0], units="degC")
        prob.set_val("working_fluid:mass_flow_in", [40.0, 18.0], units="kg/s")
        prob.run_model()

        def get(name, units=None):
            return prob.get_val(f"shell_tube_hx.{name}", units=units)

        process_temp_out = get("process_fluid:temperature_out", units="degC")
        working_temp_out = get("working_fluid:temperature_out", units="degC")
        process_mass_flow_out = get("process_fluid:mass_flow_out", units="kg/s")
        working_mass_flow_out = get("working_fluid:mass_flow_out", units="kg/s")
        process_pressure_out = get("process_fluid:pressure_out", units="bar")
        working_pressure_out = get("working_fluid:pressure_out", units="bar")
        dp_process_Pa = get("pressure_drop_process_fluid", units="Pa")
        dp_working_Pa = get("pressure_drop_working_fluid", units="Pa")

        rel = 1e-8
        with subtests.test("roles_swapped flag"):
            assert get("roles_swapped") == approx([0.0, 1.0])

        with subtests.test("process fluid heats up when swapped"):
            assert process_temp_out[1] > 30.0
        with subtests.test("working fluid cools down when swapped"):
            assert working_temp_out[1] < 90.0

        with subtests.test("swapped process_fluid:temperature_out mirrors nominal working"):
            assert process_temp_out[1] == approx(working_temp_out[0], rel=rel)
        with subtests.test("swapped working_fluid:temperature_out mirrors nominal process"):
            assert working_temp_out[1] == approx(process_temp_out[0], rel=rel)

        with subtests.test("swapped pressure_drop_process_fluid mirrors nominal working"):
            assert dp_process_Pa[1] == approx(dp_working_Pa[0], rel=rel)
        with subtests.test("swapped pressure_drop_working_fluid mirrors nominal process"):
            assert dp_working_Pa[1] == approx(dp_process_Pa[0], rel=rel)

        with subtests.test("swapped outlet pressures reflect remapped pressure drops"):
            assert process_pressure_out[1] == approx(1.0 - dp_working_Pa[0] / 1e5, rel=rel)
            assert working_pressure_out[1] == approx(1.0 - dp_process_Pa[0] / 1e5, rel=rel)

        with subtests.test("mass flow is conserved per stream when swapped"):
            assert process_mass_flow_out[1] == approx(40.0, rel=1e-12)
            assert working_mass_flow_out[1] == approx(18.0, rel=1e-12)

        for name in [
            "total_heat_transfer_rate",
            "hx_effectiveness",
            "number_of_transfer_units",
            "heat_capacity_rate_ratio",
            "overall_heat_transfer_coefficient",
            "pump_power",
            "entropy_generation_rate",
            "exergy_destruction_rate",
        ]:
            with subtests.test(f"{name} unchanged by swap"):
                values = get(name)
                assert values[1] == approx(values[0], rel=rel)

    def test_hx_config_temperature_limits(self, shell_tube_hx_config, subtests):
        """Default inlet temperatures must be in the fluid's single-phase liquid range."""
        invalid_cases = {
            "process fluid frozen": ({"process_fluid_temp_C": -5.0}, "process_fluid_temp_C"),
            "working fluid below triple point": (
                {"working_fluid_temp_C": 0.0},
                "working_fluid_temp_C",
            ),
            "process fluid boiling at 1 bar": (
                {"process_fluid_temp_C": 100.0},
                "process_fluid_temp_C",
            ),
            "working fluid boiling at 0.04 bar": (
                {"working_fluid_temp_C": 30.0, "working_fluid_pressure_bar": 0.04},
                "working_fluid_temp_C",
            ),
        }
        for name, (overrides, match) in invalid_cases.items():
            with subtests.test(name):
                with pytest.raises(ValueError, match=match):
                    self._create_problem(shell_tube_hx_config, **overrides)

        with subtests.test("above 100 degC is valid at higher pressure"):
            prob = self._create_problem(
                shell_tube_hx_config, process_fluid_temp_C=120.0, process_fluid_pressure_bar=3.0
            )
            assert prob.get_val("shell_tube_hx.process_fluid:temperature_in")[0] == 120.0

    def test_hx_inlet_guardrails(self, shell_tube_hx_config, subtests):
        """Non-physical inlet values raise an AnalysisError naming the offending timestep."""
        invalid_cases = {
            "negative process mass flow": ("process_fluid:mass_flow_in", -5.0, "must be > 0"),
            "zero working mass flow": ("working_fluid:mass_flow_in", 0.0, "must be > 0"),
            "zero process pressure": ("process_fluid:pressure_in", 0.0, "must be > 0 bar"),
            "negative working pressure": ("working_fluid:pressure_in", -1.0, "must be > 0 bar"),
            "NaN process temperature": ("process_fluid:temperature_in", np.nan, "must be finite"),
            "inf working mass flow": ("working_fluid:mass_flow_in", np.inf, "must be finite"),
            "frozen working fluid": ("working_fluid:temperature_in", -5.0, "minimum temperature"),
            "boiling process fluid": ("process_fluid:temperature_in", 120.0, "boiling point"),
        }
        for name, (var, bad_value, match) in invalid_cases.items():
            with subtests.test(name):
                prob = self._create_problem(shell_tube_hx_config, n_timesteps=2)
                values = prob.get_val(var).copy()
                values[1] = bad_value
                prob.set_val(var, values)
                with pytest.raises(om.AnalysisError, match=rf"{var}.*{match}.*timestep\(s\) \[1\]"):
                    prob.run_model()

    def test_hx_outlet_pressure_guardrail(self, shell_tube_hx_config):
        """A pressure drop larger than the inlet pressure raises an AnalysisError."""
        prob = self._create_problem(shell_tube_hx_config)
        prob.set_val("process_fluid:temperature_in", 50.0, units="degC")
        prob.set_val("process_fluid:pressure_in", 0.2, units="bar")
        prob.set_val("process_fluid:mass_flow_in", 60.0, units="kg/s")
        with pytest.raises(om.AnalysisError, match=r"process_fluid pressure drop .* exceeds"):
            prob.run_model()

    def test_hx_solve_failure_reports_timestep(self, shell_tube_hx_config):
        """Solver trial temperatures outside the CoolProp range raise an AnalysisError."""
        prob = self._create_problem(
            shell_tube_hx_config, working_fluid_mass_flow_kg_s=18.0, L_tube_m=30.0
        )
        with pytest.raises(om.AnalysisError, match="steady solve failed at timestep 0"):
            prob.run_model()

    def test_hx_no_heat_transfer(self, shell_tube_hx_config, subtests):
        """Equal (or nearly equal) inlet temperatures pass through with no heat transfer.

        Timestep 0 is nominal, timestep 1 has equal inlet temperatures, and timestep 2 has
        inlet temperatures within ``min_inlet_temp_diff_K`` (0.01 K by default).
        """
        prob = self._create_problem(shell_tube_hx_config, n_timesteps=3)
        prob.set_val("process_fluid:temperature_in", [90.0, 30.0, 30.005], units="degC")
        with pytest.warns(UserWarning, match=r"no heat transfer at timestep\(s\) \[1, 2\]"):
            prob.run_model()

        def get(name, units=None):
            return prob.get_val(f"shell_tube_hx.{name}", units=units)

        with subtests.test("no_heat_transfer flag"):
            assert get("no_heat_transfer") == approx([0.0, 1.0, 1.0])
        with subtests.test("solver_warning flag"):
            assert get("solver_warning") == approx([0.0, 0.0, 0.0])

        with subtests.test("nominal timestep unaffected"):
            assert get("total_heat_transfer_rate", units="kW")[0] == approx(
                2462.235075109509, rel=1e-5
            )

        with subtests.test("outlet temperatures equal inlet temperatures"):
            assert get("process_fluid:temperature_out", units="degC")[1:] == approx(
                [30.0, 30.005], rel=1e-12
            )
            assert get("working_fluid:temperature_out", units="degC")[1:] == approx(
                [30.0, 30.0], rel=1e-12
            )

        for name in [
            "total_heat_transfer_rate",
            "hx_effectiveness",
            "number_of_transfer_units",
            "overall_heat_transfer_coefficient",
            "entropy_generation_rate",
            "exergy_destruction_rate",
        ]:
            with subtests.test(f"{name} is zero"):
                assert get(name)[1:] == approx([0.0, 0.0])

        with subtests.test("heat_capacity_rate_ratio still computed"):
            C_r = get("heat_capacity_rate_ratio")[1:]
            assert np.all((C_r > 0.0) & (C_r <= 1.0))

        dp_process = get("pressure_drop_process_fluid", units="Pa")
        dp_working = get("pressure_drop_working_fluid", units="Pa")
        with subtests.test("pressure drops and pump power still computed"):
            assert np.all(dp_process[1:] > 0.0)
            assert np.all(dp_working[1:] > 0.0)
            assert np.all(get("pump_power", units="kW")[1:] > 0.0)

        with subtests.test("outlet pressures reflect pressure drops"):
            assert get("process_fluid:pressure_out", units="bar")[1:] == approx(
                1.0 - dp_process[1:] / 1e5, rel=1e-10
            )
            assert get("working_fluid:pressure_out", units="bar")[1:] == approx(
                1.0 - dp_working[1:] / 1e5, rel=1e-10
            )

    def test_hx_pinch_warning(self, shell_tube_hx_config, subtests):
        """A temperature approach below pinch_threshold_K is reported, not flagged unreliable."""
        prob = self._create_problem(shell_tube_hx_config, process_fluid_mass_flow_kg_s=2.0)
        with pytest.warns(UserWarning, match=r"pinch_threshold_K .* at timestep\(s\) \[0\]"):
            prob.run_model()

        with subtests.test("solver_warning not set for pinch"):
            assert prob.get_val("shell_tube_hx.solver_warning")[0] == 0.0
        with subtests.test("results still computed"):
            assert prob.get_val("shell_tube_hx.total_heat_transfer_rate")[0] > 0.0
