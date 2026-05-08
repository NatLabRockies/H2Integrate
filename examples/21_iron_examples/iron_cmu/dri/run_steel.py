from h2integrate import H2IntegrateModel


config_path = "single_site_steel.yaml"
model = H2IntegrateModel(config_path)
model.setup()
model.run()
model.post_process()
