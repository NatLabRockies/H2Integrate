import os
from pathlib import Path

from h2integrate.core.utilities import load_yaml
from h2integrate.core.h2integrate_model import H2IntegrateModel


os.chdir(Path(__file__).parent)

driver_config = load_yaml(Path(__file__).parent / "driver_config.yaml")
tech_config = load_yaml(Path(__file__).parent / "tech_config.yaml")
plant_config = load_yaml(Path(__file__).parent / "plant_config.yaml")

h2i_config = {
    "name": "H2Integrate_config",
    "system_summary": "",
    "driver_config": driver_config,
    "technology_config": tech_config,
    "plant_config": plant_config,
}
# Create a H2I model
h2i = H2IntegrateModel(h2i_config)

# Run the model
h2i.run()

h2i.post_process()
