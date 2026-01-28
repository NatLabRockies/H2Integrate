from pathlib import Path

import numpy as np
from attrs import field, define
from wombat import Simulation
from wombat.core.library import load_yaml

from h2integrate.core.utilities import merge_shared_inputs
from h2integrate.converters.hydrogen.pem_electrolyzer import (
    ECOElectrolyzerPerformanceModel,
    ECOElectrolyzerPerformanceModelConfig,
)


@define(kw_only=True)
class WOMBATModelConfig(ECOElectrolyzerPerformanceModelConfig):
    """
    library_path: Path to the WOMBAT library directory, relative from this file
    if not an absolute path.
    cost_year: dollar-year corresponding to capex value.
    """

    library_path: Path = field()
    cost_year: int = field(converter=int)


class WOMBATElectrolyzerModel(ECOElectrolyzerPerformanceModel):
    """
    WOMBATElectrolyzerModel is a joint performance and cost model for electrolyzers
    using the WOMBAT simulation framework.

    This class extends ECOElectrolyzerPerformanceModel and configures the WOMBAT model based
    on provided technology configuration inputs. It sets up output variables related to
    electrolyzer performance, including capacity factor, CapEx, OpEx, percent hydrogen
    lost due to operations and maintenance (O&M), and electrolyzer availability.
    """

    def setup(self):
        super().setup()
        self.config = WOMBATModelConfig.from_dict(
            merge_shared_inputs(self.options["tech_config"]["model_inputs"], "performance")
        )
        plant_life = int(self.options["plant_config"]["plant"]["plant_life"])
        self.add_output("capacity_factor", val=0.0, units=None)
        self.add_output("CapEx", val=0.0, units="USD", desc="Capital expenditure")
        self.add_output("OpEx", val=0.0, units="USD/year", desc="Operational expenditure")
        self.add_output(
            "VarOpEx",
            val=0.0,
            shape=plant_life,
            units="USD/year",
            desc="Variable operational expenditure",
        )
        self.add_discrete_output("cost_year", val=0, desc="Dollar year for costs")
        self.add_output(
            "percent_hydrogen_lost",
            val=0.0,
            units="percent",
            desc="Percent hydrogen lost due to O&M maintenance",
        )
        self.add_output(
            "electrolyzer_availability", val=0.0, units=None, desc="Electrolyzer availability"
        )

    def compute(self, inputs, outputs, discrete_inputs, discrete_outputs):
        super().compute(inputs, outputs, discrete_inputs, discrete_outputs)

        # Ensure library_path is a Path object
        library_path = self.config.library_path
        if not isinstance(library_path, Path):
            library_path = Path(library_path)
        # Determine the correct library path: use as-is if absolute, else relative to this file
        if library_path.is_absolute():
            library_path = library_path
        else:
            library_path = Path(__file__).parents[3] / library_path

        wombat_config = load_yaml(library_path, "electrolyzer.yml")

        # do a manual check to make sure that stack_capacity_kw * n_stacks is equal to the rating
        stack_capacity_mw = (
            wombat_config["electrolyzers"]["central_electrolyzer"]["stack_capacity_kw"] * 1e-3
        )
        n_stacks = wombat_config["electrolyzers"]["central_electrolyzer"]["n_stacks"]

        rating_from_config = self.config.n_clusters * self.config.cluster_rating_MW
        if rating_from_config != stack_capacity_mw * n_stacks:
            raise ValueError(
                f"Electrolyzer rating {rating_from_config} does not match the product of "
                f"stack capacity {stack_capacity_mw} and number of stacks "
                f"{n_stacks} in the WOMBAT config. "
                "Ensure that the rating is equal to stack_capacity_kw * n_stacks."
            )

        sim = Simulation(
            library_path=library_path,
            config=wombat_config,
            random_seed=314,
        )

        # WOMBAT expects 8760 hours to simulate one year of operation.
        sim.run(delete_logs=True, save_metrics_inputs=False, until=8760)

        scaling_factor = rating_from_config  # The baseline electrolyzer in WOMBAT is 1MW

        # TODO: handle cases where the project is longer than one year.
        # Do the project and divide by the project lifetime using sim.env.simulation_years

        # Only support single electrolyzer systems for now, check the size of the returned values
        availability_values = sim.metrics.operations[sim.metrics.electrolyzer_id].values
        if availability_values.shape[1] > 1:
            raise ValueError("Only single electrolyzer systems are supported at this time.")
        availability = availability_values.flatten()

        original_hydrogen_out = outputs["hydrogen_out"].copy()

        # Adjust hydrogen_out by availability
        hydrogen_out_with_availability = outputs["hydrogen_out"] * availability

        # Update outputs["hydrogen_out"] with the available hydrogen
        outputs["hydrogen_out"] = hydrogen_out_with_availability

        # Compute total hydrogen produced (sum over the year)
        outputs["total_hydrogen_produced"] = np.sum(hydrogen_out_with_availability)

        # Compute percent hydrogen lost due to O&M maintenance
        percent_hydrogen_lost = 100 * (
            1 - outputs["total_hydrogen_produced"] / np.sum(original_hydrogen_out)
        )

        outputs["percent_hydrogen_lost"] = percent_hydrogen_lost

        # We're currently grabbing the annual measure and since we're enforcing a single year,
        # that's fine. In the future we may need to adjust this to handle multiple years and
        # output OpEx as an array.
        outputs["CapEx"] = self.config.electrolyzer_capex * rating_from_config * 1e3
        outputs["OpEx"] = sim.metrics.opex("annual").squeeze() * scaling_factor
        outputs["electrolyzer_availability"] = sim.metrics.time_based_availability(
            "annual", "electrolyzer"
        ).squeeze()

        sim.metrics.potential[sim.metrics.electrolyzer_id] = np.atleast_2d(original_hydrogen_out).T
        sim.metrics.production[sim.metrics.electrolyzer_id] = np.atleast_2d(
            hydrogen_out_with_availability
        ).T

        # CF calculation goes here
        outputs["capacity_factor"] = sim.metrics.capacity_factor(
            which="net", frequency="project", by="electrolyzer"
        ).squeeze()

        discrete_outputs["cost_year"] = self.config.cost_year
