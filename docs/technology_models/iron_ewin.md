# Iron electrowinning models

H2I contains models to simulate to separation of mostly pure iron from iron oxides.
The main input feedstock is iron ore, while the output commodity is "sponge iron", i.e. iron that is typically brittle ("spongey") and contains less carbon than most steel alloys.
This sponge iron can then be used in an electric arc furnace (EAF) to produce steel.

There are currently three iron electrowinning processes modeled in H2I:
    - Aqueous Hydroxide Electrolysis (AHE)
    - Molten Salt Electrolysis (MSE)
    - Molten Oxide Electrolysis (MOE)

In reality, the exact composition and structure of the resulting sponge iron will differ depending on the process and the conditions.
Currently, H2I models do not make these distinctions, as the technology is new and we are still building out the capability.
Instead, the models in their current form are based on two recent studies of electrowinning technology as a whole.

The first study is by [Humbert et al.](doi.org/10.1007/s40831-024-00878-3), who focus specifically on iron and the three technologies above.
These authors gather information on the specific energy required for electrolysis and associated pretreatments needed, which is applied in the `humbert_electrowinning_performance` performance model.
In their supporting information, they also model the full operational expenditures for each process, which is applied in the `humbert_stinn_electrowinning_cost` cost model.

The second study is by [Stinn & Allanore](doi.org/10.1149.2/2.F06202IF), who present a generalized capital cost model for electrowinning of many different metals.
These authors use both cost data and physical parameters from existing studies to fit the model to be applicable to any metal, including iron.
This model is applied in the `humbert_stinn_electrowinning_cost` cost model.

To use this model, specify `"humbert_electrowinning_performance"` as the performance model and `"humbert_stinn_electrowinning_cost"` as the cost model.

## Shared Parameters

- `electrolysis_type`: The type of electrolysis used for electrowinning. Options are:
    - `"ahe"`: Aqueous Hydroxide Electrolysis
    - `"mse"`: Molten Salt Electrolysis
    - `"moe"`: Molten Oxide Electrolysis

# Performance Parameters

- `ore_fe_wt_pct`: The percentage by weight of iron in the input ore.
- `capacity_mw`: The electrical capacity in MW of the electrowinning plant.

## Cost Parameters

None. The `cost_year` is automatically set to 2018 to match the Stinn/Allanore source values. Be sure to set `target_dollar_year` in the `finanace_parameters` to match your desired output dollar year in the finance calculations.

## Required Feedstocks

- `iron_ore_in`: Iron ore to be used for electrowinning.
- `electricity_in`: Electricity used to reduce iron ore to sponge iron.
