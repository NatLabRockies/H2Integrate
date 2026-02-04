import openmdao.api as om
import matplotlib.pyplot as plt
from ard.viz.layout import plot_layout  # a plotting tool!

from h2integrate.core.h2integrate_model import H2IntegrateModel


# Create the model
h2i_model = H2IntegrateModel("./h2i_inputs/wind_pv_battery.yaml")

# Run the model
h2i_model.run()

# Post-process the results
h2i_model.post_process()

show_visualizations = False
if show_visualizations:
    # get the Ard sub-problem
    ard_prob = h2i_model.prob.model.plant.wind.wind.ard_sub_prob._subprob

    # create an N2 diagram of the H2I problem
    om.n2(h2i_model.prob, outfile="n2-h2i.html")

    # create an N2 diagram of the Ard sub-problem
    om.n2(ard_prob, outfile="n2-ard.html")

    # visualize the wind farm layout
    ard_input = h2i_model.technology_config["technologies"]["wind"]["model_inputs"][
        "performance_parameters"
    ]["ard_system"]
    plot_layout(
        ard_prob,
        input_dict=ard_input,
        show_image=True,
        include_cable_routing=True,
    )
    plt.show()
