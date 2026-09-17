from h2integrate import H2IntegrateModel


h2i = H2IntegrateModel("solar_battery_grid.yaml")
h2i.run()
h2i.post_process()
