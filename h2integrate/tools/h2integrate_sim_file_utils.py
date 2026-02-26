from pathlib import Path

import dill


def load_dill_pickle(filepath):
    """
    Load a dill pickle file from the given filepath.

    Args:
        filepath (str or Path): The path to the dill pickle file.

    Returns:
        Any: The data loaded from the dill pickle file.
    """
    if isinstance(filepath, str):
        filepath = Path(filepath)
    with Path.open(filepath, "rb") as f:
        data = dill.load(f)
    return data


def save_pickle_data(output_data_dict, config, pkl_fn):
    """
    Save data to pickle files in specified directories.

    Args:
        output_data_dict (dict): Dictionary where keys are output names and
            values are the data to be pickled.
        config (object): Configuration object that contains the attribute
            `run_full_simulation_fn` which specifies the base directory for saving files.
        pkl_fn (str): Filename for the pickle file.
    """
    for output_name, data in output_data_dict.items():
        path = Path(config.run_full_simulation_fn) / Path(output_name)
        path.mkdir(parents=True, exist_ok=True)
        filepath = path / Path(pkl_fn)
        with Path.open(filepath, "wb") as f:
            dill.dump(data, f)


def save_pickle_data_iron_out(output_data_dict, config, pkl_fn):
    """
    Save data to pickle files in specified directories.

    Args:
        output_data_dict (dict): Dictionary where keys are output names and
            values are the data to be pickled.
        config (object): Configuration object that contains the attribute
            `iron_out_fn` which specifies the base directory for saving files.
        pkl_fn (str): Filename for the pickle file.
    """
    for output_name, data in output_data_dict.items():
        path = Path(config.iron_out_fn) / Path(output_name)
        path.mkdir(parents=True, exist_ok=True)
        filepath = path / Path(pkl_fn)
        with Path.open(filepath, "wb") as f:
            dill.dump(data, f)


def save_physics_results_h2integrate_setup(config, wind_cost_results):
    """
    Save physics results for H2Integrate setup.
    This function saves the physics results and configuration data needed for
    future runs in a pickle file. The filename is generated based on the
    latitude, longitude, and year from the configuration.

    Args:
        config (object): Configuration object containing simulation settings.
        wind_cost_results (object): Results of the wind cost calculations.
    Returns:
        None
    """
    # from setup_h2integrate_simulation() if config.save_pre_iron (line 556)
    lat = config.hopp_config["site"]["data"]["lat"]
    lon = config.hopp_config["site"]["data"]["lon"]
    year = config.hopp_config["site"]["data"]["year"]
    site_res_id = f"{lat:.3f}_{lon:.3f}_{year:d}"

    # Write outputs needed for future runs in .pkls
    pkl_fn = site_res_id + ".pkl"
    output_names = ["config", "wind_cost_results"]
    output_data = [config, wind_cost_results]
    output_data_dict = dict(zip(output_names, output_data))

    save_pickle_data(output_data_dict, config, pkl_fn)


def load_physics_h2integrate_setup(config):
    """
    Loads the physics setup for the H2Integrate simulation from previously saved pickle files.

    Args:
        config: A configuration object that contains the simulation settings, including:

            - hopp_config: A dictionary with site data, including latitude ('lat'),
                longitude ('lon'), and year ('year').
            - run_full_simulation_fn: A string representing the path to the directory where
                simulation results are stored.

    Returns:
        tuple: A tuple containing:

            - config: The loaded configuration object from the pickle file.
            - wind_cost_results: The loaded wind cost results from the pickle file.
    """
    lat = config.hopp_config["site"]["data"]["lat"]
    lon = config.hopp_config["site"]["data"]["lon"]
    year = config.hopp_config["site"]["data"]["year"]
    site_res_id = f"{lat:.3f}_{lon:.3f}_{year:d}"

    # Read in outputs from previously-saved .pkls
    pkl_fn = site_res_id + ".pkl"
    config_fpath = config.run_full_simulation_fn / "config" / pkl_fn
    wind_cost_fpath = config.run_full_simulation_fn / "wind_cost_results" / pkl_fn
    config = load_dill_pickle(config_fpath)
    wind_cost_results = load_dill_pickle(wind_cost_fpath)

    return config, wind_cost_results


def save_physics_results_h2integrate_simulation(
    config,
    lcoh,
    lcoe,
    electrolyzer_physics_results,
    wind_annual_energy_kwh,
    solar_pv_annual_energy_kwh,
    energy_shortfall_hopp,
):
    """
    Save the physics results of the H2Integrate simulation to a pickle file.

    Args:
        config (dict): Configuration dictionary containing simulation settings.
        lcoh (float): Levelized cost of hydrogen.
        lcoe (float): Levelized cost of energy.
        electrolyzer_physics_results (dict): Results from the electrolyzer physics simulation.
        wind_annual_energy_kwh (float): Annual wind energy production in kWh.
        solar_pv_annual_energy_kwh (float): Annual solar PV energy production in kWh.
        energy_shortfall_hopp (float): Energy shortfall from the HOPP simulation.
    Returns:
        None
    """
    # from setup_h2integrate_simulation() if config.save_pre_iron (line 1071)
    lat = config.hopp_config["site"]["data"]["lat"]
    lon = config.hopp_config["site"]["data"]["lon"]
    year = config.hopp_config["site"]["data"]["year"]
    site_res_id = f"{lat:.3f}_{lon:.3f}_{year:d}"

    # Write outputs needed for future runs in .pkls
    pkl_fn = site_res_id + ".pkl"
    output_names = [
        "lcoe",
        "lcoh",
        "electrolyzer_physics_results",
        "wind_annual_energy_kwh",
        "solar_pv_annual_energy_kwh",
        "energy_shortfall_hopp",
    ]
    output_data = [
        lcoe,
        lcoh,
        electrolyzer_physics_results,
        wind_annual_energy_kwh,
        solar_pv_annual_energy_kwh,
    ]
    output_data_dict = dict(zip(output_names, output_data))

    save_pickle_data(output_data_dict, config, pkl_fn)


def load_physics_h2integrate_simulation(config):
    """
    Load physics simulation results for a H2Integrate simulation.
    This function reads in outputs from previously-saved .pkl files based on the
    configuration provided. It loads various simulation results including LCOH,
    LCOE, electrolyzer physics results, wind annual energy, and solar PV annual energy.
    Args:
        config (object): Configuration object containing simulation parameters and file paths.
    Returns:
        tuple: A tuple containing the following elements:
            - lcoh (object): Loaded LCOH data.
            - lcoe (object): Loaded LCOE data.
            - electrolyzer_physics_results (object): Loaded electrolyzer physics results.
            - wind_annual_energy_kwh (object): Loaded wind annual energy in kWh.
            - solar_pv_annual_energy_kwh (object): Loaded solar PV annual energy in kWh.
    """
    lat = config.hopp_config["site"]["data"]["lat"]
    lon = config.hopp_config["site"]["data"]["lon"]
    year = config.hopp_config["site"]["data"]["year"]
    site_res_id = f"{lat:.3f}_{lon:.3f}_{year:d}"

    # Read in outputs from previously-saved .pkls
    pkl_fn = site_res_id + ".pkl"
    lcoh_fpath = config.run_full_simulation_fn / "lcoh" / pkl_fn
    lcoe_fpath = config.run_full_simulation_fn / "lcoe" / pkl_fn
    elec_phys_fpath = config.run_full_simulation_fn / "electrolyzer_physics_results" / pkl_fn
    wind_fpath = config.run_full_simulation_fn / "wind_annual_energy_kwh" / pkl_fn
    solar_fpath = config.run_full_simulation_fn / "solar_pv_annual_energy_kwh" / pkl_fn
    lcoh = load_dill_pickle(lcoh_fpath)
    lcoe = load_dill_pickle(lcoe_fpath)
    electrolyzer_physics_results = load_dill_pickle(elec_phys_fpath)
    wind_annual_energy_kwh = load_dill_pickle(wind_fpath)
    solar_pv_annual_energy_kwh = load_dill_pickle(solar_fpath)

    return (
        lcoh,
        lcoe,
        electrolyzer_physics_results,
        wind_annual_energy_kwh,
        solar_pv_annual_energy_kwh,
    )


def save_iron_ore_results(
    config, iron_ore_config, iron_ore_performance, iron_ore_costs, iron_ore_finance
):
    """
    Save iron ore results to a pickle file.
    This function saves the performance, costs, and finance data of iron ore to a pickle file
    based on the configuration provided. The output file is named using the latitude, longitude,
    and year from the configuration.

    Args:
        config (object): Configuration object containing the output directory and site data.
        iron_ore_config (dict): Configuration dictionary specific to iron ore.
        iron_ore_performance (object): Object containing iron ore performance data.
        iron_ore_costs (object): Object containing iron ore costs data.
        iron_ore_finance (object): Object containing iron ore finance data.
    Raises:
        ValueError: If the output directory is not set in the configuration.
    """
    if config.iron_out_fn is None:
        raise ValueError("config.iron_out_fn is not set. Please set the output directory.")
    # lat = config.hopp_config["site"]["data"]["lat"]
    # lon = config.hopp_config["site"]["data"]["lon"]
    year = config.hopp_config["site"]["data"]["year"]
    perf_df = iron_ore_performance.performances_df.set_index("Name")
    perf_ds = perf_df.loc[:, iron_ore_config["iron_ore"]["site"]["name"]]
    lat = perf_ds["Latitude"]
    lon = perf_ds["Longitude"]

    site_res_id = f"{lat:.3f}_{lon:.3f}_{year:d}"
    pkl_fn = f"{site_res_id}.pkl"
    output_names = ["iron_ore_performance", "iron_ore_costs", "iron_ore_finance"]
    output_data = [iron_ore_performance, iron_ore_costs, iron_ore_finance]
    output_data_dict = dict(zip(output_names, output_data))

    save_pickle_data_iron_out(output_data_dict, config, pkl_fn)


def save_iron_results(config, iron_performance, iron_costs, iron_finance, iron_CI=None):
    """
    Saves the iron results to a pickle file.

    Args:
        config (object): Configuration object containing the output directory and site data.
        iron_performance (any): Performance data of the iron.
        iron_costs (any): Cost data of the iron.
        iron_finance (any): Financial data of the iron.
        iron_CI (any, optional): Confidence interval data of the iron. Defaults to None.
    Raises:
        ValueError: If the output file name in the configuration is not set.
    """
    if config.iron_out_fn is None:
        raise ValueError("config.iron_out_fn is not set. Please set the output directory.")

    lat = config.hopp_config["site"]["data"]["lat"]
    lon = config.hopp_config["site"]["data"]["lon"]
    year = config.hopp_config["site"]["data"]["year"]
    site_res_id = f"{lat:.3f}_{lon:.3f}_{year:d}"
    pkl_fn = f"{site_res_id}.pkl"

    output_names = ["iron_performance", "iron_costs", "iron_finance"]
    output_data = [iron_performance, iron_costs, iron_finance]
    if iron_CI is not None:
        output_names.append("iron_CI")
        output_data.append(iron_CI)
    output_data_dict = dict(zip(output_names, output_data))

    save_pickle_data_iron_out(output_data_dict, config, pkl_fn)
