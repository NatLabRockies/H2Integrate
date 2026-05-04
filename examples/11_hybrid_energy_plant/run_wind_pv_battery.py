from h2integrate import H2IntegrateModel


# Create a GreenHEART model
h2i = H2IntegrateModel("wind_pv_battery.yaml")

# Run the model
h2i.run()

h2i.post_process()
