from h2integrate import H2IntegrateModel


h2i = H2IntegrateModel("wind_plant_electrolyzer.yaml")

# Run the model
h2i.run()

h2i.post_process()
