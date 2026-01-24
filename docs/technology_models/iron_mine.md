# Iron mine model

H2I contains an iron mine model that simulates the extraction of crude ore and its processing into iron ore pellets.
The main input feedstock is `crude_ore`, i.e. the unprocessed ore in the earth containing iron oxide.
The output commodity is `iron_ore` in the form of pellets that can be shipped to other plants for further processing (`iron_plant` for instance).

This model was developed in conjunction with the University of Minnesota's Natural Resource Research Institute (NRRI).
NRRI compiled cost and production data from 5 existing mines and provided expertise for analysis at NLR to determine the energy input and cost trends across these mines.
Four of the mines (Northshore, United, Hibbing, and Minorca) are located in Minnesota, while one (Tilden) is located in Michigan.

There are two potential grades of ore produced from an iron mine in this model:
- Standard or Blast Furnace (BF) grade pellets (62-65% Fe)
- Direct Reduction (DR) grade pellets (>67% Fe)

It was determined that 3 of these mines (Northshore, United, and Hibbing) had crude reserves sufficient to produce DR-grade pellets, although only one (Northshore) reported production data on DR-grade pellets, with the rest reporting their data strictly on standard ore pellets.
The increases in cost and energy usage reported at the Northshore mine were used to project the potential performance and cost of DR-grade production at United and Hibbing.
The results of this analysis are compiled in the directory `h2integreate/converters/iron/martin_ore/`.
Performance data are included in `perf_inputs.csv`, with cost data in `cost_inputs.csv`.

These data were compiled from two sources:
- The EPA's "Taconite Iron Ore NESHAP Economic Impact Analysis" by [Heller et al.](https://www.epa.gov/sites/default/files/2020-07/documents/taconite_eia_neshap_final_08-2003.pdf) - Capex estimates
    - This document esitmated the total percentage of cost spent throughout the entire industry on capital as a percentage of total production costs - 5.4%. This percentage is applied to the total annual production costs of each plant to find the estimated Capex.
- Cleveland-Cliffs Inc.'s Technical Report Summaries for individual mines - Opex and performance data
    - [Northshore Mine](https://minedocs.com/22/Northshore-TR-12312021.pdf)
    - [United Mine](https://minedocs.com/22/United-Taconite-TR-12312021.pdf)
    - [Hibbing Mine](https://minedocs.com/22/Hibbing-Taconite-TR-12312021.pdf)
    - [Minorca Mine](https://minedocs.com/22/Minorca-TR-12312021.pdf)
    - [Tilden Mine](https://minedocs.com/22/Tilden-TR-12312021.pdf)

To use this model, specify `"iron_mine_performance_martin"` as the performance model and `"iron_mine_cost_martin"` as the cost model.
Currently, no complex calculations occur beyond importing performance and costs.
In the performance model, the "wet long tons" (wlt) that ore production is typically reported in are converted to dry metric tons for use in H2I.
In the cost model, the total capex costs for a plant are scaled by the amount of are produced annualy.
Besides these calculations, previously-calculated performance and cost metrics are simply loaded from the input spreadsheets.
