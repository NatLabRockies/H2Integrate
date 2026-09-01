from h2integrate import H2IntegrateModel


h2i_model = H2IntegrateModel("offshore_plant_oae.yaml")

# Run the model
h2i_model.run()

# Post-process the results
h2i_model.post_process()
