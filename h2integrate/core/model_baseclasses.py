import copy
import hashlib
from pathlib import Path

import dill
import openmdao.api as om
from attrs import field, define

from h2integrate.core.utilities import BaseConfig


class PerformanceModelBaseClass(om.ExplicitComponent):
    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        # Below should be done in subclass that produces hydrogen
        # self.commodity = "hydrogen"
        # self.commodity_rate_units = "kg/h"
        # self.commodity_amount_units = "kg"
        # super().setup()

        # Below should be done in subclass that produces electricity
        # self.commodity = "electricity"
        # self.commodity_rate_units = "kW"
        # self.commodity_amount_units = "kW*h"
        # super().setup()

        # n_timesteps is number of timesteps in a simulation
        self.n_timesteps = self.options["plant_config"]["plant"]["simulation"]["n_timesteps"]
        # dt is seconds per timestep
        self.dt = self.options["plant_config"]["plant"]["simulation"]["dt"]
        # plant_life is number of years the plant is expected to operate for
        self.plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        hours_per_year = 8760
        # hours simulated is the number of hours in a simulation
        hours_simulated = (self.dt / 3600) * self.n_timesteps
        # fraction_of_year_simulated is the ratio of simulation length to length of year
        # and may be used to estimate annual performance from simulation performance
        self.fraction_of_year_simulated = hours_simulated / hours_per_year
        self.set_outputs()

    def set_outputs(self):
        # Check that the required attributes have been instantiated
        required = ("commodity", "commodity_rate_units", "commodity_amount_units")
        missing = [el for el in required if not hasattr(self, el)]

        if missing:
            # Throw error if any attributes are missing.
            cls_name = self.msginfo.split("<class ")[-1].strip("<>")
            missing = ", ".join(missing)
            msg = (
                f"{cls_name} is missing the following required attributes: {missing}."
                f"Please ensure that the attributes: {missing}"
                f"are set in the `setup()` method of {cls_name}."
                "Further documentation can be found in the `PerformanceModelBaseClass` "
                "documentation."
            )
            raise NotImplementedError(msg)

        # timeseries profiles
        self.add_output(
            f"{self.commodity}_out",
            val=0.0,
            shape=self.n_timesteps,
            units=self.commodity_rate_units,
        )
        # sum over simulation
        self.add_output(
            f"total_{self.commodity}_produced", val=0.0, units=self.commodity_amount_units
        )
        # annual performance estimate for commodity produced
        self.add_output(
            f"annual_{self.commodity}_produced",
            val=0.0,
            shape=self.plant_life,
            units=f"({self.commodity_amount_units})/year",
        )
        # lifetime estimate of item replacements, represented as a fraction of the capacity.
        self.add_output("replacement_schedule", val=0.0, shape=self.plant_life, units="unitless")
        # capacity factor is the ratio of actual production / maximum production possible
        self.add_output(
            "capacity_factor",
            val=0.0,
            shape=self.plant_life,
            units="unitless",
            desc="Capacity factor",
        )
        # rated/maximum commodity production, this would be used to calculate the maximum
        # production possible over the simulation
        self.add_output(
            f"rated_{self.commodity}_production", val=0.0, units=self.commodity_rate_units
        )
        # operational life of the technology if the technology cannot be replaced
        self.add_output("operational_life", val=self.plant_life, units="yr")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


@define(kw_only=True)
class CostModelBaseConfig(BaseConfig):
    cost_year: int = field(converter=int)


class CostModelBaseClass(om.ExplicitComponent):
    """Baseclass to be used for all cost models. The built-in outputs
    are used by the finance model and must be outputted by all cost models.

    Subclasses should use CostModelBaseConfig for their configuration class.

    Outputs:
        - CapEx (float): capital expenditure costs in $
        - OpEx (float): annual fixed operating expenditure costs in $/year
        - VarOpEx (float): annual variable operating expenditure costs in $/year

    Discrete Outputs:
        - cost_year (int): dollar-year corresponding to CapEx and OpEx values.
            This may be inherent to the cost model, or may depend on user provided input values.
    """

    def initialize(self):
        self.options.declare("driver_config", types=dict)
        self.options.declare("plant_config", types=dict)
        self.options.declare("tech_config", types=dict)

    def setup(self):
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        # Define outputs: CapEx and OpEx costs
        self.add_output("CapEx", val=0.0, units="USD", desc="Capital expenditure")
        self.add_output("OpEx", val=0.0, units="USD/year", desc="Fixed operational expenditure")
        self.add_output(
            "VarOpEx",
            val=0.0,
            shape=plant_life,
            units="USD/year",
            desc="Variable operational expenditure",
        )
        # Define discrete outputs: cost_year
        self.add_discrete_output(
            "cost_year", val=self.config.cost_year, desc="Dollar year for costs"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


@define(kw_only=True)
class ResizeablePerformanceModelBaseConfig(BaseConfig):
    size_mode: str = field(default="normal")
    flow_used_for_sizing: str | None = field(default=None)
    max_feedstock_ratio: float = field(default=1.0)
    max_commodity_ratio: float = field(default=1.0)

    def __attrs_post_init__(self):
        """Validate sizing parameters after initialization."""
        valid_modes = ["normal", "resize_by_max_feedstock", "resize_by_max_commodity"]
        if self.size_mode not in valid_modes:
            raise ValueError(
                f"Sizing mode '{self.size_mode}' is not a valid sizing mode. "
                f"Options are {valid_modes}."
            )

        if self.size_mode != "normal":
            if self.flow_used_for_sizing is None:
                raise ValueError(
                    "'flow_used_for_sizing' must be set when size_mode is "
                    "'resize_by_max_feedstock' or 'resize_by_max_commodity'"
                )


class ResizeablePerformanceModelBaseClass(PerformanceModelBaseClass):
    """Baseclass to be used for all resizeable performance models. The built-in inputs
    are used by the performance models to resize themselves.

    These parameters are all set as attributes within the config class, which inherits from
    ResizeablePerformanceModelBaseConfig

    Discrete Inputs:
        - size_mode (str): The mode in which the component is sized. Options:
            - "normal": The component size is taken from the tech_config.
            - "resize_by_max_feedstock": The component size is calculated relative to the
                maximum available amount of a certain feedstock or feedstocks
            - "resize_by_max_commodity": The electrolyzer size is calculated relative to the
                maximum amount of the commodity used by another tech
        - flow_used_for_sizing (str): The feedstock/commodity flow used to determine the plant size
            in "resize_by_max_feedstock" and "resize_by_max_commodity" modes

    Inputs:
        - max_feedstock_ratio (float): The ratio of the max feedstock that can be consumed by
            this component to the max feedstock available.
        - max_commodity_ratio (float): The ratio of the max commodity that can be produced by
            this component to the max commodity consumed by the downstream tech.
    """

    def setup(self):
        super().setup()
        # Parse in sizing parameters
        size_mode = self.config.size_mode
        self.add_discrete_input("size_mode", val=size_mode)

        if size_mode not in ["normal", "resize_by_max_feedstock", "resize_by_max_commodity"]:
            raise ValueError(
                f"Sizing mode '{size_mode}' is not a valid sizing mode."
                " Options are 'normal', 'resize_by_max_feedstock',"
                "'resize_by_max_commodity'."
            )

        if size_mode != "normal":
            if self.config.flow_used_for_sizing is not None:
                size_flow = self.config.flow_used_for_sizing
                self.add_discrete_input("flow_used_for_sizing", val=size_flow)
            else:
                raise ValueError(
                    "'flow_used_for_sizing' must be set when size_mode is "
                    "'resize_by_max_feedstock' or 'resize_by_max_commodity'"
                )
            if size_mode == "resize_by_max_commodity":
                comm_ratio = self.config.max_commodity_ratio
                self.add_input("max_commodity_ratio", val=comm_ratio, units="unitless")
            else:
                feed_ratio = self.config.max_feedstock_ratio
                self.add_input("max_feedstock_ratio", val=feed_ratio, units="unitless")

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Computation for the OM component.

        For a template class this is not implement and raises an error.
        """

        raise NotImplementedError("This method should be implemented in a subclass.")


@define(kw_only=True)
class CacheBaseConfig(BaseConfig):
    enable_caching: bool = field()
    cache_dir: str | Path = field()

    def __attrs_post_init__(self):
        # Convert cache directory to Path object
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)

        # Create a cache directory if it doesn't exist
        if self.enable_caching and not self.cache_dir.exists():
            self.cache_dir.mkdir(parents=True, exist_ok=True)


class CacheBaseClass(om.ExplicitComponent):
    """Baseclass with methods to cache results and load data from cached results.

    Subclasses should have a corresponding config class that inherits
    `CacheBaseConfig`.
    """

    def set_outputs_from_cache_dict(self, cached_dict, outputs, discrete_outputs={}):
        """Set outputs and discrete_outputs using previously cached data available in cached_dict.

        Args:
            cached_dict (dict): dictionary with top-level keys of "outputs" and "discrete_outputs".
                Top-level values are dictionaries with keys corresponding to output of discrete
                output names and values of the resulting output value.
            outputs (om.vectors.default_vector.DefaultVector): OM outputs of `compute()` method.
                The output values are set the outputs have been previously cached.
            discrete_outputs (om.core.component._DictValues, optional): OM discrete outputs of
                `compute()` method. Defaults to {}.
        """
        # Set outputs to the outputs saved in the cached results
        for output_name, default_output_val in outputs.items():
            outputs[output_name] = cached_dict.get("outputs", {}).get(
                output_name, default_output_val
            )

        # Set discrete outputs to the outputs saved in the cached results
        for discrete_output_name, discrete_default_output_val in discrete_outputs.items():
            discrete_outputs[output_name] = cached_dict.get("discrete_outputs", {}).get(
                discrete_output_name, discrete_default_output_val
            )
        return

    def create_cache_dict_from_outputs(self, outputs, discrete_outputs={}):
        """Create a dictionary of outputs and discrete outputs. The outputs and discrete_outputs
        should be set in the `compute()` prior to this function being called.

        Args:
            outputs (om.vectors.default_vector.DefaultVector): OM outputs of `compute()` method
                that have already been set with the resulting values.
            discrete_outputs (om.core.component._DictValues, optional): OM discrete outputs of
                `compute()` method that have been set with resulting values. Defaults to {}.

        Returns:
            dict: dictionary with top-level keys of "outputs" and "discrete_outputs".
                Top-level values are dictionaries with keys corresponding to output of discrete
                output names and values of the resulting output value.
        """
        cache_dict = {
            "outputs": dict(outputs.items()),
            "discrete_outputs": dict(discrete_outputs.items()),
        }
        return cache_dict

    def load_outputs(
        self, inputs, outputs, discrete_inputs={}, discrete_outputs={}, config_dict: dict = {}
    ):
        """Load previously cached computation results if they exist.

        This method generates a unique cache filename based on the current inputs and
        configuration, then checks if cached results exist for this exact combination.
        If cached results are found, the output and discrete_output values are populated
        from the cache file and the method returns True to indicate the computation can
        be skipped. If no cache file exists or caching is disabled, the method returns
        False to indicate the computation must be performed.

        Args:
            inputs (om.vectors.default_vector.DefaultVector): OM inputs to `compute()` method.
            outputs (om.vectors.default_vector.DefaultVector): OM outputs of `compute()` method.
                The output values are set the results that have been previously cached.
            discrete_inputs (om.core.component._DictValues, optional): OM discrete inputs to
                `compute()` method. Defaults to {}.
            discrete_outputs (om.core.component._DictValues, optional): OM discrete outputs of
                `compute()` method. The discrete_output values are set to the discrete_outputs
                have been previously cached. Defaults to {}.
            config_dict (dict, optional): dictionary created/updated from config class.
                Defaults to {}. If config_dict is input as an empty dictionary,
                config_dict is created from `self.config.as_dict()`

        Returns:
            bool: True if outputs were set to cached results. False if cache file
                doesn't exist and the model still needs to calculate and set the outputs.
        """

        # If not caching is not enabled, return False to indicate that outputs have not been set
        if not self.config.enable_caching:
            return False

        # If caching is enabled, check if file exists with cached results

        # Check if config_dict was input as an empty dictionary
        if not bool(config_dict):
            # If it was, create config_dict from config attribute
            config_dict = self.config.as_dict()

        # Create unique filename for cached results based on inputs and config
        cache_filename = self.make_cache_hash_filename(config_dict, inputs, discrete_inputs)

        # Check if file exists that contains cached results
        if not cache_filename.exists():
            # If file doesn't exist, return False to indicate that outputs have not been set
            return False

        # Load the cached results
        cache_path = Path(cache_filename)
        with cache_path.open("rb") as f:
            cached_data = dill.load(f)

        # Set outputs to the outputs saved in the cached results
        self.set_outputs_from_cache_dict(cached_data, outputs, discrete_outputs)

        # Return True to indicate that outputs have been set from cached results
        return True

    def cache_outputs(
        self, inputs, outputs, discrete_inputs={}, discrete_outputs={}, config_dict: dict = {}
    ):
        """Save computation results to cache for future reuse.

        This method generates a unique cache filename based on the current inputs and
        configuration, then serializes the output and discrete_output values to a pickle file.
        This allows future computations with identical inputs and configuration to skip the
        calculation by loading from cache instead. The outputs and discrete_outputs must already
        be set with their computed values before before calling this method. If caching is
        disabled, this method returns immediately without saving anything.

        Args:
            inputs (om.vectors.default_vector.DefaultVector): OM inputs to `compute()` method
            outputs (om.vectors.default_vector.DefaultVector): OM outputs of `compute()` method
                that have already been set with the resulting values
            discrete_inputs (om.core.component._DictValues, optional): OM discrete inputs to
                `compute()` method. Defaults to {}.
            discrete_outputs (om.core.component._DictValues, optional): OM discrete_outputs of
                `compute()` method that have already been set with the resulting values.
                Defaults to {}.
            config_dict (dict, optional): dictionary created/updated from config class.
                Defaults to {}. If config_dict is input as an empty dictionary,
                config_dict is created from `self.config.as_dict()`
        """
        # If not caching is not enabled, return without caching outputs
        if not self.config.enable_caching:
            return

        # Cache the results for future use if caching is enabled

        # Check if config_dict was input as an empty dictionary
        if not bool(config_dict):
            # Create config_dict from config attribute
            config_dict = self.config.as_dict()

        # Create unique filename for cached results based on inputs and config
        cache_filename = self.make_cache_hash_filename(config_dict, inputs, discrete_inputs)

        cache_path = Path(cache_filename)

        # Create dictionary of outputs and discrete_outputs
        output_dict = self.create_cache_dict_from_outputs(outputs, discrete_outputs)

        # Save outputs and discrete_outputs to pickle file
        with cache_path.open("wb") as f:
            dill.dump(output_dict, f)

    def make_cache_hash_filename(self, config, inputs, discrete_inputs={}):
        """Make valid filepath to a pickle file with a filename that is unique based on information
        available in the config, inputs, and discrete inputs.

        Args:
            config (object | dict): configuration object that inherits `BaseConfig` or dictionary.
            inputs (om.vectors.default_vector.DefaultVector): OM inputs to `compute()` method
            discrete_inputs (om.core.component._DictValues, optional): OM discrete inputs to
                `compute()` method. Defaults to {}.

        Returns:
            Path: filepath to pickle file with filename as unique cache key.
        """
        # NOTE: maybe would be good to add a string input that can specify what model this
        # cache is for (like "hopp" or "floris"), this could be used in the cache
        # filename but perhaps unnecessary

        if not isinstance(config, dict):
            config_dict = config.as_dict()
        else:
            config_dict = copy.deepcopy(config)

        hash_dict_str = str(config_dict)
        hash_dict_str += str(dict(inputs.items()))
        hash_dict_str += str(dict(discrete_inputs.items()))

        # Create a unique hash for the current configuration to use as a cache key
        config_hash = hashlib.md5(hash_dict_str.encode("utf-8")).hexdigest()

        return self.config.cache_dir / f"{config_hash}.pkl"

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        """
        Computation for the OM component.
        This template includes commented out code on how to use the functionality
        of this base class within a subclass.

        Please ensure this method is implemented in a subclass.
        """

        # # 1. Check if this combination of inputs and parameters has been run before
        # loaded_results = self.load_outputs(inputs, outputs, discrete_inputs, discrete_outputs)
        # if loaded_results:
        #     # Case has been run before and outputs have been set, can exit this function
        #     return

        # # 2. Run compute() method as normal and set outputs. For example:
        # outputs['my_output_var'] = inputs['my_input_var']*10

        # # 3. Save outputs to cache directory
        # self.cache_outputs(inputs, outputs, discrete_inputs, discrete_outputs)

        raise NotImplementedError("This method should be implemented in a subclass.")
