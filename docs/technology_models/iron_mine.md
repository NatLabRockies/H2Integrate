# Iron mine model

H2I contains 2 iron mine models that simulate the extraction of crude ore and its processing into iron ore pellets:
    - `SimpleIronMine`: Models only the flow of `crude_ore` in and `iron_ore` out, with costs all lumped together
    - `NRRIIronMine`: Models mass flows and electricity/fuel consumption at intermediate steps, with costs broken out

## SimpleIronMine
The main input feedstock is `crude_ore`, i.e. the unprocessed ore in the earth containing iron oxide.
The output commodity is `iron_ore` in the form of pellets that can be shipped to other plants (e.g. `iron_plant`) for further processing.

This model was developed in conjunction with the [University of Minnesota's Natural Resource Research Institute (NRRI)](https://www.nrri.umn.edu/).
NRRI compiled cost and production data from 5 existing mines and provided expertise for analysis at NLR to determine the energy input and cost trends across these mines.
Four of the mines (Northshore, United, Hibbing, and Minorca) are located in Minnesota, while one (Tilden) is located in Michigan.

There are two potential grades of ore produced from an iron mine in this model:
- Standard or Blast Furnace (BF) grade pellets (62-65% Fe)
- Direct Reduction (DR) grade pellets (>67% Fe)

It was determined that 3 of these mines (Northshore, United, and Hibbing) had crude reserves sufficient to produce DR-grade pellets, although only one (Northshore) reported production data on DR-grade pellets, with the rest reporting their data strictly on standard ore pellets.
The increases in cost and energy usage reported at the Northshore mine were used to project the potential performance and cost of DR-grade production at United and Hibbing.
The results of this analysis are compiled in the directory `h2integrate/converters/iron/simple_ore/`.
Performance data are included in `perf_inputs.csv` with cost data in `cost_inputs.csv`.

These data were compiled from two sources:
- The EPA's "Taconite Iron Ore NESHAP Economic Impact Analysis" by [Heller et al.](https://www.epa.gov/sites/default/files/2020-07/documents/taconite_eia_neshap_final_08-2003.pdf) - Capex estimates
    - This document estimated the total percentage of cost spent throughout the entire industry on capital as a percentage of total production costs - 5.4%. This percentage is applied to the total annual production costs of each plant to find the estimated Capex.
- Cleveland-Cliffs Inc.'s Technical Report Summaries for individual mines - Opex and performance data
    - [Northshore Mine](https://minedocs.com/22/Northshore-TR-12312021.pdf)
    - [United Mine](https://minedocs.com/22/United-Taconite-TR-12312021.pdf)
    - [Hibbing Mine](https://minedocs.com/22/Hibbing-Taconite-TR-12312021.pdf)
    - [Minorca Mine](https://minedocs.com/22/Minorca-TR-12312021.pdf)
    - [Tilden Mine](https://minedocs.com/22/Tilden-TR-12312021.pdf)

To use this model, specify `"SimpleIronMinePerformanceComponent"` as the performance model and `"SimpleIronMineCostComponent"` as the cost model.
Currently, no complex calculations occur beyond importing performance and costs.
In the performance model, the "wet long tons" (wlt) that ore production is typically reported in are converted to dry metric tons for use in H2I.
In the cost model, the total capex costs for a plant are scaled by the amount of are produced annually.
Besides these calculations, previously-calculated performance and cost metrics are simply loaded from the input spreadsheets.

## NRRIIronMine
The main inputs are `electricity` and `fuel`.
The output commodity is `iron_ore` in the form of pellets that can be shipped to other plants (e.g. `iron_plant`) for further processing.

This model was developed in conjunction with the [University of Minnesota's Natural Resource Research Institute (NRRI)](https://www.nrri.umn.edu/), led by Kimberly Anderson <kimander@d.umn.edu>

This model splits out the separate processes to produce iron ore pellets at a mine (mining, comminution, beneficiation, pelletization) and tracks the material flows.

Sources (2021 costs):
    - [SEC S-K 1300 Tilden Mining Company](https://www.sec.gov/Archives/edgar/data/764065/000076406522000037/clf-2021123110xkex965.htm)
    - [SEC S-K 1300 Hibbing Taconite](https://www.sec.gov/Archives/edgar/data/764065/000076406522000033/a20220211-8xkxex961.htm)
    - [SEC S-K 1300 United Taconite](https://www.sec.gov/Archives/edgar/data/764065/000076406522000033/a20220211-8xkxex964.htm)
    - [SEC S-K 1300 Minorca Mine](https://www.sec.gov/Archives/edgar/data/764065/000076406522000033/a20220211-8xkxex962.htm)
    - [SEC S-K 1300 Northshore Mining Company](https://www.sec.gov/Archives/edgar/data/764065/000076406522000033/a20220211-8xkxex963.htm)

Local electricity costs (2012):
    - [Tilden Estimated Electrical Costs](https://www.electricitylocal.com/states/michigan/marquette/)
    - [Hibtac Estimate Electrical Costs](https://www.electricitylocal.com/states/minnesota/hibbing/)
    - [Utac Estimated Electrical Costs](https://www.electricitylocal.com/states/minnesota/virginia/)
    - [Minora Estimated Electrical Costs](https://www.electricitylocal.com/states/minnesota/virginia/)
    - [Northshore - Babbitt Electrical Costs](https://www.electricitylocal.com/states/minnesota/babbitt/)
    - [Northshore - Silver Bay Electrical Costs](https://www.electricitylocal.com/states/minnesota/silver-bay/)
    - All inflated to 2021 costs using electricity [CPI](https://fred.stlouisfed.org/series/CUUR0000SEHF01):
        - 2012 average electricity CPI: 196.6298
        - 2021 average electricity CPI: 223.8915833

Estimated electrical breakdown data synthesized using Gemini and ChatGPT and verified using:
    - Prediction of fuel consumption of mining dump trucks: A neural networks approach Elnaz Siami-Irdemoosa, Saeid Dindarloo, Applied Energy 151, 2015, pp. 77-84
    - US DOE - Critical Minerals & Energy Innovation under Lawrence Berkeley National Laboratory under Contract DE-AC02-05CH11231 (January 2026)
    - The Effects of Increasing Costs of the Future Relation Between Open Pit and Underground Mining, Dan Nilsson, 1982. US Dept of Interior - Office of Surface Mining - Bureau of Mines under Grand No. OSM G5105032

Fuel Costs (2021):
    - Natural Gas:
        - MN industrial NG $5.47/tcf [EIA](https://www.eia.gov/dnav/ng/ng_pri_sum_dcu_smn_a.htm)
        - 1.037 MMBtu/tcf
        - Final NG price: $5.275/MMBtu
    - Diesel:
        - MN pump diesel $3.208/gal [MN Dept. of Revenue](https://www.revenue.state.mn.us/petroleum-tax-eia-average-retail-fuel-price)
        - minus est. $0.285/gal MN excise tax [MN Dept. of Revenue](https://www.revenue.state.mn.us/petroleum-tax-fuel-excise-tax-rates-and-fees)
        - minus $0.244/gal federal tax [EIA](https://www.eia.gov/tools/faqs/faq.php?id=10&t=5)
        - Final off road diesel price: $2.679/gal
