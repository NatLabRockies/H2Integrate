"""
This file is based on the WISDEM file of the same name: https://github.com/WISDEM/WISDEM
and also based off of the H2Integrate file of the same name originally adapted by Jared Thomas.
"""

import re
import warnings
from pathlib import Path

import openmdao.api as om

from h2integrate.core.utilities import check_file_format_for_csv_generator


class PoseOptimization:
    """
    This class contains a collection of methods for setting up an OpenMDAO
    optimization problem for a H2Integrate simulation.

    Args:
        config: instance of a H2Integrate config containing all desired simulation set up
    """

    def __init__(self, config):
        """
        This method primarily establishes lists of optimization methods
        available through different optimization drivers"""

        self.config = config

        self.scipy_methods = [
            "SLSQP",
            "Nelder-Mead",
            "COBYLA",
        ]

        self.pyoptsparse_methods = [
            "SNOPT",
            "CONMIN",
            "NSGA2",
        ]

    def get_number_design_variables(self):
        """
        This method counts the number of design variables required given
        the provided set up and returns the result

        Returns:
            int: number of design variables
        """
        # Determine the number of design variables
        n_DV = 0

        if self.config["design_variables"]["electrolyzer_rating_kw"]["flag"]:
            n_DV += 1
        if self.config["design_variables"]["pv_capacity_kw"]["flag"]:
            n_DV += 1
        if self.config["design_variables"]["wave_capacity_kw"]["flag"]:
            n_DV += 1
        if self.config["design_variables"]["battery_capacity_kw"]["flag"]:
            n_DV += 1
        if self.config["design_variables"]["battery_capacity_kwh"]["flag"]:
            n_DV += 1

        # Wrap-up at end with multiplier for finite differencing
        if "form" in self.config["driver"]["optimization"].keys():
            if (
                self.config["driver"]["optimization"]["form"] == "central"
            ):  # TODO this should probably be handled at the MPI point to avoid confusion with n_DV being double what would be expected
                n_DV *= 2

        return n_DV

    def _get_step_size(self):
        """
        If a step size for the driver-level finite differencing is provided,
        use that step size. Otherwise use a default value.

        Returns:
            step size (float): step size for optimization
        """

        if "step_size" not in self.config["driver"]["optimization"]:
            step_size = 1.0e-6
            warnings.warn(
                f"Step size was not specified, setting step size to {step_size}. \
                Step size may be set in the h2integrate \
                config file under opt_options/driver/optimization/step_size \
                and should be of type float",
                UserWarning,
            )
        else:
            step_size = self.config["driver"]["optimization"]["step_size"]

        return step_size

    def _set_optimizer_properties(
        self, opt_prob, options_keys=[], opt_settings_keys=[], mapped_keys={}
    ):
        """Set the optimizer properties, both the `driver.options` and
        `driver.opt_settings`. See OpenMDAO documentation on drivers
        to determine which settings are set by either options or
        opt_settings.

        Args:
            opt_prob (OpenMDAO problem object):  The hybrid plant OpenMDAO problem object.
            options_keys (list, optional): List of keys for driver opt_settings
                to be set. Defaults to [].
            opt_settings_keys (list, optional): List of keys for driver options
                to be set. Defaults to [].
            mapped_keys (dict, optional): Key pairs where the yaml name differs
                from what's expected
                                          by the driver. Specifically, the key
                                          is what's given in the yaml
                                          and the value is what's expected by
                                          the driver. Defaults to {}.

        Returns:
            opt_prob (OpenMDAO problem object): The updated openmdao problem
                object with driver settings applied.
        """

        opt_options = self.config["driver"]["optimization"]

        # Loop through all of the options provided and set them in the OM driver object
        for key in options_keys:
            if key in opt_options:
                if key in mapped_keys:
                    opt_prob.driver.options[mapped_keys[key]] = opt_options[key]
                else:
                    opt_prob.driver.options[key] = opt_options[key]

        # Loop through all of the opt_settings provided and set them in the OM driver object
        for key in opt_settings_keys:
            if key in opt_options:
                if key in mapped_keys:
                    opt_prob.driver.opt_settings[mapped_keys[key]] = opt_options[key]
                else:
                    opt_prob.driver.opt_settings[key] = opt_options[key]

        return opt_prob

    def set_driver(self, opt_prob):
        """set which optimization driver to use and set options

        Args:
            opt_prob (openmdao problem instance): openmdao problem class instance
                for current optimization problem

        Raises:
            ImportError: An optimization algorithm from pyoptsparse was selected,
                but pyoptsparse is not installed
            ImportError: An optimization algorithm from pyoptsparse was selected,
                but the algorithm code is not currently installed within pyoptsparse
            ImportError: An optimization algorithm was requested from NLopt, but
                NLopt is not currently installed.
            ValueError: The selected optimizer is not yet supported.
            Exception: The specified generator type for the OpenMDAO design
                of experiments is unsupported.

        Returns:
            opt_prob (openmdao problem instance): openmdao problem class instance,
                edited from input with desired driver and driver options
        """

        folder_output = self.config["general"]["folder_output"]

        if self.config["driver"].get("optimization", {}).get("flag", False):
            opt_options = self.config["driver"]["optimization"]
            step_size = self._get_step_size()

            if "step_calc" in opt_options.keys():
                if opt_options["step_calc"] == "None":
                    step_calc = None
                else:
                    step_calc = opt_options["step_calc"]
            else:
                step_calc = None

            if "form" in opt_options.keys():
                if opt_options["form"] == "None":
                    form = None
                else:
                    form = opt_options["form"]
            else:
                form = None

            opt_prob.model.approx_totals(
                method="fd", step=step_size, form=form, step_calc=step_calc
            )

            # Set optimization solver and options. First, Scipy's SLSQP and COBYLA
            if opt_options["solver"] in self.scipy_methods:
                opt_prob.driver = om.ScipyOptimizeDriver()
                opt_prob.driver.options["optimizer"] = opt_options["solver"]

                options_keys = ["tol", "max_iter", "disp"]
                opt_settings_keys = ["rhobeg", "catol", "adaptive"]
                mapped_keys = {"max_iter": "maxiter"}
                opt_prob = self._set_optimizer_properties(
                    opt_prob, options_keys, opt_settings_keys, mapped_keys
                )

            # The next two optimization methods require pyOptSparse.
            elif opt_options["solver"] in self.pyoptsparse_methods:
                try:
                    from openmdao.api import pyOptSparseDriver
                except RuntimeError:
                    raise ImportError(
                        f"You requested the optimization solver {opt_options['solver']}, \
                        but you have not installed pyOptSparse. \
                        Please do so and rerun."
                    ) from None
                opt_prob.driver = pyOptSparseDriver(gradient_method=opt_options["gradient_method"])

                try:
                    opt_prob.driver.options["optimizer"] = opt_options["solver"]
                except ImportError:
                    raise ImportError(
                        f"You requested the optimization solver {opt_options['solver']}, \
                        but you have not installed it within pyOptSparse. \
                        Please build {opt_options['solver']} and rerun."
                    ) from None

                # Most of the pyOptSparse options have special syntax when setting them,
                # so here we set them by hand instead of using
                # `_set_optimizer_properties` for SNOPT and CONMIN.
                if opt_options["solver"] == "CONMIN":
                    opt_prob.driver.opt_settings["ITMAX"] = opt_options["max_iter"]

                if opt_options["solver"] == "NSGA2":
                    opt_settings_keys = [
                        "PopSize",
                        "maxGen",
                        "pCross_real",
                        "pMut_real",
                        "eta_c",
                        "eta_m",
                        "pCross_bin",
                        "pMut_bin",
                        "PrintOut",
                        "seed",
                        "xinit",
                    ]
                    opt_prob = self._set_optimizer_properties(
                        opt_prob, opt_settings_keys=opt_settings_keys
                    )

                elif opt_options["solver"] == "SNOPT":
                    opt_prob.driver.opt_settings["Major optimality tolerance"] = float(
                        opt_options["tol"]
                    )
                    opt_prob.driver.opt_settings["Major iterations limit"] = int(
                        opt_options["max_major_iter"]
                    )
                    opt_prob.driver.opt_settings["Iterations limit"] = int(
                        opt_options["max_minor_iter"]
                    )
                    opt_prob.driver.opt_settings["Major feasibility tolerance"] = float(
                        opt_options["tol"]
                    )
                    if "time_limit" in opt_options:
                        opt_prob.driver.opt_settings["Time limit"] = int(opt_options["time_limit"])
                    opt_prob.driver.opt_settings["Summary file"] = (
                        Path(folder_output) / "SNOPT_Summary_file.txt"
                    )
                    opt_prob.driver.opt_settings["Print file"] = (
                        Path(folder_output) / "SNOPT_Print_file.txt"
                    )
                    if "hist_file_name" in opt_options:
                        opt_prob.driver.hist_file = opt_options["hist_file_name"]
                    if "verify_level" in opt_options:
                        opt_prob.driver.opt_settings["Verify level"] = opt_options["verify_level"]
                    else:
                        opt_prob.driver.opt_settings["Verify level"] = -1
                if "hotstart_file" in opt_options:
                    opt_prob.driver.hotstart_file = opt_options["hotstart_file"]

            elif opt_options["solver"] == "GA":
                opt_prob.driver = om.SimpleGADriver()
                options_keys = [
                    "Pc",
                    "Pm",
                    "bits",
                    "compute_pareto",
                    "cross_bits",
                    "elitism",
                    "gray",
                    "max_gen",
                    "multi_obj_exponent",
                    "multi_obj_weights",
                    "penalty_exponent",
                    "penalty_parameter",
                    "pop_size",
                    "procs_per_model",
                    "run_parallel",
                ]
                opt_prob = self._set_optimizer_properties(opt_prob, options_keys)

            else:
                raise ValueError(f"Optimizer {opt_options['solver']} is not yet supported.")

            if opt_options["debug_print"]:
                opt_prob.driver.options["debug_print"] = [
                    "desvars",
                    "ln_cons",
                    "nl_cons",
                    "objs",
                    "totals",
                ]

        elif self.config["driver"].get("design_of_experiments", False):
            if self.config["driver"]["design_of_experiments"]["flag"]:
                doe_options = self.config["driver"]["design_of_experiments"]
                if doe_options["generator"].lower() == "uniform":
                    generator = om.UniformGenerator(
                        num_samples=int(doe_options["num_samples"]),
                        seed=doe_options["seed"],
                    )
                elif doe_options["generator"].lower() == "fullfact":
                    generator = om.FullFactorialGenerator(levels=int(doe_options["levels"]))
                elif doe_options["generator"].lower() == "plackettburman":
                    generator = om.PlackettBurmanGenerator()
                elif doe_options["generator"].lower() == "boxbehnken":
                    generator = om.BoxBehnkenGenerator()
                elif doe_options["generator"].lower() == "latinhypercube":
                    generator = om.LatinHypercubeGenerator(
                        samples=int(doe_options["num_samples"]),
                        criterion=doe_options["criterion"],
                        seed=doe_options["seed"],
                    )
                elif doe_options["generator"].lower() == "csvgen":
                    valid_file = check_file_format_for_csv_generator(
                        doe_options["filename"], self.config, check_only=True
                    )
                    if not valid_file:
                        raise UserWarning(
                            f"There may be issues with the csv file {doe_options['filename']}, "
                            f"which may cause errors within OpenMDAO. "
                            "To check this csv file or create a new one, run the function "
                            "h2integrate.core.utilities.check_file_format_for_csv_generator()."
                        )
                    generator = om.CSVGenerator(
                        filename=doe_options["filename"],
                    )
                else:
                    raise Exception(
                        "The generator type {} is unsupported.".format(doe_options["generator"])
                    )

                # Initialize driver
                opt_prob.driver = om.DOEDriver(generator)

                if doe_options["debug_print"]:
                    opt_prob.driver.options["debug_print"] = [
                        "desvars",
                        "ln_cons",
                        "nl_cons",
                        "objs",
                    ]

                # options
                if "run_parallel" in doe_options:
                    opt_prob.driver.options["run_parallel"] = doe_options["run_parallel"]

        else:
            warnings.warn(
                "Design variables are set to be optimized or studied, but no driver is selected. "
                "If you want to run an optimization, please enable a driver.",
                UserWarning,
            )

        return opt_prob

    def set_objective(self, opt_prob):
        """Set merit figure. Each objective has its own scaling.  Check first for user override.

        The optimization is always minimizing the objective. If you wish to maximize the objective,
        use a negative ref or scaler value in the config.

        Args:
            opt_prob (openmdao problem instance): openmdao problem instance for
                current optimization problem

        Returns:
            opt_prob (openmdao problem instance): openmdao problem instance for
                current optimization problem with objective set
        """
        if self.config.get("objective", False):
            if "ref" in self.config["objective"]:
                ref = self.config["objective"]["ref"]
            else:
                ref = None
            opt_prob.model.add_objective(
                self.config["objective"]["name"],
                ref=ref,
            )

        return opt_prob

    def set_design_variables(self, opt_prob):
        """Set optimization design variables.

        Args:
            opt_prob (openmdao problem instance): openmdao problem instance for
                current optimization problem

        Returns:
            opt_prob (openmdao problem instance): openmdao problem instance for
                current optimization problem with design variables set
        """

        for technology, variables in self.config["design_variables"].items():
            for key, value in variables.items():
                if value["flag"]:
                    value.pop("flag")
                    opt_prob.model.add_design_var(f"{technology}.{key}", **value)

        return opt_prob

    def set_constraints(self, opt_prob):
        """sets up optimization constraints for the h2integrate optimization problem

        Args:
            opt_prob (openmdao problem instance): openmdao problem instance for
                current optimization problem

        Raises:
            Exception: all design variables must have at least one of an upper
                and lower bound specified

        Returns:
            opt_prob (openmdao problem instance): openmdao problem instance for
                current optimization problem edited to include constraint setup
        """
        if self.config.get("constraints", False):
            for technology, variables in self.config["constraints"].items():
                for key, value in variables.items():
                    if value["flag"]:
                        value.pop("flag")
                        opt_prob.model.add_constraint(f"{technology}.{key}", **value)

    def set_recorders(self, opt_prob):
        """sets up a recorder for the openmdao problem as desired in the input yaml

        Args:
            opt_prob (openmdao problem instance): openmdao problem instance
                for current optimization problem

        Returns:
            opt_prob (openmdao problem instance): openmdao problem instance for
                current optimization problem edited to include a set up recorder
        """
        folder_output = self.config["general"]["folder_output"]

        # Set recorder on the OpenMDAO driver level using the `optimization_log`
        # filename supplied in the optimization yaml
        recorder_options = ["record_inputs", "record_outputs", "record_residuals"]

        if self.config["recorder"].get("flag", False):
            # Check that the output folder exists and create it if needed
            if not Path(folder_output).exists():
                Path.mkdir(folder_output, parents=True, exist_ok=True)

            overwrite_recorder = self.config["recorder"].get("overwrite_recorder", False)
            recorder_path = Path(folder_output) / self.config["recorder"]["file"]

            if not overwrite_recorder:
                # make a unique filename with the same base as self.config["recorder"]["file"]
                # separate out the filename without the extension
                file_base = self.config["recorder"]["file"].split(".sql")[0]
                # get all the files in the output folder that start with file_base
                existing_files = list(Path(folder_output).glob(f"{file_base}*"))
                if len(existing_files) > 0:
                    # if file(s) exist with the same base name, make a new unique filename

                    # get past numbers that were used to make unique files by matching
                    # filenames against the file base name followed by a number
                    past_numbers = [
                        int(re.findall(f"{file_base}[0-9]+", str(fname))[0].split(file_base)[-1])
                        for fname in existing_files
                        if len(re.findall(f"{file_base}[0-9]+", str(fname))) > 0
                    ]

                    if len(past_numbers) > 0:
                        # if multiple files have the same basename followed by a number,
                        # take the maximum unique number and add one
                        unique_number = int(max(past_numbers) + 1)
                        recorder_path = Path(folder_output) / f"{file_base}{unique_number}.sql"
                    else:
                        # if no files have the same basename followed by a number,
                        # but do have the same basename, then add a zero to the file basename
                        recorder_path = Path(folder_output) / f"{file_base}0.sql"

            recorder_attachment = (
                self.config["recorder"].get("recorder_attachment", "driver").lower()
            )
            allowed_attachments = ["driver", "model"]
            if recorder_attachment not in allowed_attachments:
                msg = (
                    f"Invalid recorder attachment '{recorder_attachment}'. "
                    f"Currently supported options are {allowed_attachments}. "
                    "We recommend using 'driver' if running an optimization or DOE in parallel."
                )
                raise ValueError(msg)

            # Create recorder
            recorder = om.SqliteRecorder(recorder_path)

            if recorder_attachment == "model":
                # add the recorder to the model
                recorder_options += ["options_excludes"]

                opt_prob.model.add_recorder(recorder)

                for recorder_opt in recorder_options:
                    if recorder_opt in self.config["recorder"]:
                        opt_prob.model.recording_options[recorder_opt] = self.config[
                            "recorder"
                        ].get(recorder_opt)

                opt_prob.model.recording_options["includes"] = self.config["recorder"].get(
                    "includes", ["*"]
                )
                opt_prob.model.recording_options["excludes"] = self.config["recorder"].get(
                    "excludes", ["*resource_data"]
                )
                return recorder_path

            if recorder_attachment == "driver":
                recorder_options += [
                    "record_constraints",
                    "record_derivative",
                    "record_desvars",
                    "record_objectives",
                ]
                # add the recorder to the driver
                opt_prob.driver.add_recorder(recorder)

                for recorder_opt in recorder_options:
                    if recorder_opt in self.config["recorder"]:
                        opt_prob.driver.recording_options[recorder_opt] = self.config[
                            "recorder"
                        ].get(recorder_opt)

                opt_prob.driver.recording_options["includes"] = self.config["recorder"].get(
                    "includes", ["*"]
                )
                opt_prob.driver.recording_options["excludes"] = self.config["recorder"].get(
                    "excludes", ["*resource_data"]
                )
            return recorder_path
        return None

    def set_restart(self, opt_prob):
        """
        Prepares to restart from last recorded iteration if the original
        problem was set up for warm start

        Args:
            opt_prob (openmdao problem instance): openmdao problem instance for
            current optimization problem

        Returns:
            opt_prob (openmdao problem instance): openmdao problem instance
                for current optimization problem set up for warm start
        """

        if "warmstart_file" in self.config["driver"]["optimization"]:
            # Directly read the pyoptsparse sqlite db file
            from pyoptsparse import SqliteDict

            db = SqliteDict(self.config["driver"]["optimization"]["warmstart_file"])

            # Grab the last iteration's design variables
            last_key = db["last"]
            desvars = db[last_key]["xuser"]

            # Obtain the already-setup OM problem's design variables
            if opt_prob.model._static_mode:
                design_vars = opt_prob.model._static_design_vars
            else:
                design_vars = opt_prob.model._design_vars

            # Get the absolute names from the promoted names within the OM model.
            # We need this because the pyoptsparse db has the absolute names for
            # variables but the OM model uses the promoted names.
            prom2abs = opt_prob.model._var_allprocs_prom2abs_list["output"]
            abs2prom = {}
            for key in design_vars:
                abs2prom[prom2abs[key][0]] = key

            # Loop through each design variable
            for key in desvars:
                prom_key = abs2prom[key]

                # Scale each DV based on the OM scaling from the problem.
                # This assumes we're running the same problem with the same scaling
                scaler = design_vars[prom_key]["scaler"]
                adder = design_vars[prom_key]["adder"]

                if scaler is None:
                    scaler = 1.0
                if adder is None:
                    adder = 0.0

                desvars[key] / scaler - adder

        return opt_prob
