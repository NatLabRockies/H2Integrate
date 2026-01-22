import pandas as pd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


myFmt = mdates.DateFormatter("%m/%d")


def plot_methanol(model):
    fig = plt.figure(figsize=(8, 8))

    times = pd.date_range("2013", periods=8760, freq="1h")

    # Electricity to H2 using Electrolyzer
    plt.subplot(3, 2, 1)
    T = plt.title("Electrolyzer")
    T.set_position([-0.2, 1.1])
    elyzer_elec_in = (
        model.plant.electrolyzer.ECOElectrolyzerPerformanceModel.get_val("electricity_in") / 1000
    )
    elyzer_h2_out = (
        model.plant.electrolyzer.ECOElectrolyzerPerformanceModel.get_val("hydrogen_out") / 1000 * 24
    )
    plt.plot(times, elyzer_elec_in, label="Electricity Available [MW]", color=[0.5, 0.5, 1])
    plt.plot(
        [times[0], times[-1]],
        [160, 160],
        "--",
        label="Electrolyzer Capacity [MW]",
        color=[0.5, 0.5, 1],
    )
    plt.plot(times, elyzer_h2_out, label="Hydrogen Produced [t/d]", color=[1, 0.5, 0])
    plt.legend(bbox_to_anchor=(0, 1.02), loc=3)
    plt.xlim(pd.to_datetime("2012-12-31"), pd.to_datetime("2013-01-31"))
    plt.xticks(["2013-01-01", "2013-01-08", "2013-01-15", "2013-01-22", "2013-01-29"])
    ax = plt.gca()
    ax.xaxis.set_major_formatter(myFmt)
    plt.xlabel("Day in simulated year")
    plt.ylabel(
        "Power\n[MW]\n \nFlow\n[t/d]", rotation="horizontal", va="center", ha="center", labelpad=20
    )

    # Electricity to CO2 using DOC
    plt.subplot(3, 2, 2)
    T = plt.title("Direct\nOcean\nCapture")
    T.set_position([-0.2, 1.1])
    doc_elec_in = model.plant.doc.direct_ocean_capture_performance.get_val("electricity_in") / 1e6
    doc_co2_out = model.plant.doc.direct_ocean_capture_performance.get_val("co2_out") / 1000
    plt.plot(times, doc_elec_in, label="Electricity Available [MW]", color=[0.5, 0.5, 1])
    plt.plot(
        [times[0], times[-1]],
        [43.32621908, 43.32621908],
        "--",
        label="DOC Input Capacity [MW]",
        color=[0.5, 0.5, 1],
    )
    plt.plot(times, doc_co2_out, label="CO$_2$ Produced [t/hr]", color=[0.5, 0.25, 0])
    plt.legend(bbox_to_anchor=(0, 1.02), loc=3)
    plt.xlim(pd.to_datetime("2012-12-31"), pd.to_datetime("2013-01-31"))
    plt.xticks(["2013-01-01", "2013-01-08", "2013-01-15", "2013-01-22", "2013-01-29"])
    ax = plt.gca()
    ax.xaxis.set_major_formatter(myFmt)
    plt.xlabel("Day in simulated year")
    plt.ylabel(
        "Power\n[MW]\n \nFlow\n[t/hr]", rotation="horizontal", va="center", ha="center", labelpad=20
    )

    # H2 and Storage
    plt.subplot(3, 2, 3)
    T = plt.title("Hydrogen\nStorage")
    T.set_position([-0.2, 1.1])
    h2_storage_in = model.plant.electrolyzer_to_h2_storage_pipe.get_val("hydrogen_in") * 3600
    h2_storage_out = model.plant.h2_storage_to_methanol_pipe.get_val("hydrogen_out") * 3600
    plt.plot(times, h2_storage_in, label="Hydrogen In [kg/hr]", color=[1, 0.5, 0])
    plt.plot(times, h2_storage_out, label="Hydrogen Out [kg/hr]", color=[0, 0.5, 0])
    plt.legend(bbox_to_anchor=(0, 1.02), loc=3)
    plt.xlim(pd.to_datetime("2012-12-31"), pd.to_datetime("2013-01-31"))
    plt.xticks(["2013-01-01", "2013-01-08", "2013-01-15", "2013-01-22", "2013-01-29"])
    ax = plt.gca()
    ax.xaxis.set_major_formatter(myFmt)
    plt.xlabel("Day in simulated year")
    plt.ylabel("Flow\n[kg/hr]", rotation="horizontal", va="center", ha="center", labelpad=20)

    # H2 and Storage
    plt.subplot(3, 2, 4)
    T = plt.title("CO$_2$\nStorage")
    T.set_position([-0.2, 1.1])
    co2_storage_in = model.plant.doc_to_co2_storage_pipe.get_val("co2_in")
    co2_storage_out = model.plant.co2_storage_to_methanol_pipe.get_val("co2_out")
    plt.plot(times, co2_storage_in, label="CO$_2$ In [kg/hr]", color=[0.5, 0.25, 0])
    plt.plot(times, co2_storage_out, label="CO$_2$ Out [kg/hr]", color=[0, 0.25, 0.5])
    plt.legend(bbox_to_anchor=(0, 1.02), loc=3)
    plt.xlim(pd.to_datetime("2012-12-31"), pd.to_datetime("2013-01-31"))
    plt.xticks(["2013-01-01", "2013-01-08", "2013-01-15", "2013-01-22", "2013-01-29"])
    ax = plt.gca()
    ax.xaxis.set_major_formatter(myFmt)
    plt.xlabel("Day in simulated year")
    plt.ylabel("Flow\n[kg/hr]", rotation="horizontal", va="center", ha="center", labelpad=20)

    # H2 and CO2 to Methanol
    plt.subplot(3, 2, 5)
    T = plt.title("Methanol")
    T.set_position([-0.2, 1.1])
    meoh_h2_in = model.plant.methanol.CO2HMethanolPlantPerformanceModel.get_val("hydrogen_in")
    meoh_co2_in = model.plant.methanol.CO2HMethanolPlantPerformanceModel.get_val("co2_in")
    meoh_meoh_out = model.plant.methanol.CO2HMethanolPlantPerformanceModel.get_val("methanol_out")
    plt.plot(times, meoh_h2_in, label="Hydrogen In [kg/hr]", color=[0, 0.5, 0])
    plt.plot(times, meoh_co2_in, label="CO$_2$ In [kg/hr]", color=[0, 0.25, 0.5])
    plt.plot(times, meoh_meoh_out, label="Methanol Out [kg/hr]", color=[1, 0, 0.5])
    plt.legend(bbox_to_anchor=(0, 1.02), loc=3)
    plt.xlim(pd.to_datetime("2012-12-31"), pd.to_datetime("2013-01-31"))
    plt.xticks(["2013-01-01", "2013-01-08", "2013-01-15", "2013-01-22", "2013-01-29"])
    ax = plt.gca()
    ax.xaxis.set_major_formatter(myFmt)
    plt.xlabel("Day in simulated year")
    plt.ylabel("Flow\n[kg/hr]", rotation="horizontal", va="center", ha="center", labelpad=20)

    # H2 and CO2 storage SOC
    plt.subplot(3, 2, 6)
    T = plt.title("State of\nCharge\n(SOC)")
    T.set_position([-0.2, 1.1])
    h2_soc = model.plant.h2_storage.get_val("hydrogen_soc") * 100
    co2_soc = model.plant.co2_storage.get_val("co2_soc") * 100
    plt.plot(times, h2_soc, label="Hydrogen SOC [%]", color=[1, 0.5, 0])
    plt.plot(times, co2_soc, label="CO$_2$ SOC [%]", color=[0.5, 0.25, 0])
    plt.legend(bbox_to_anchor=(0, 1.02), loc=3)
    plt.xlim(pd.to_datetime("2012-12-31"), pd.to_datetime("2013-01-31"))
    plt.xticks(["2013-01-01", "2013-01-08", "2013-01-15", "2013-01-22", "2013-01-29"])
    ax = plt.gca()
    ax.xaxis.set_major_formatter(myFmt)
    plt.xlabel("Day in simulated year")
    plt.ylabel("SOC\n[kg]", rotation="horizontal", va="center", ha="center", labelpad=20)

    fig.tight_layout()
    plt.show()
