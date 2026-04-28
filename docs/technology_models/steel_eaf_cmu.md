(steel-eaf-cmu)=
# CMU decarbSTEEL Electric Arc Furnace Models

H2Integrate includes two Electric Arc Furnace (EAF) performance models and a shared cost model based on the [CMU decarbSTEEL v5](https://kilthub.cmu.edu/articles/model/decarbSTEEL_Decarbonizing_Steelmaking_TechnoEconomic_EvaLuation_tool/27119169) techno-economic model developed by Carnegie Mellon University.
These models capture the energy and mass balance of steelmaking in an EAF, including slag chemistry, oxygen lancing, and electrode consumption.

The available models are:

- [`"CMUElectricArcFurnaceScrapOnlyPerformanceComponent"`](#cmu-eaf-scrap-only): EAF charged with **scrap only**.
- [`"CMUElectricArcFurnaceDRIPerformanceComponent"`](#cmu-eaf-dri): EAF charged with a **blend of DRI (sponge iron) and scrap**.
- [`"CMUElectricArcFurnaceCostModel"`](#cmu-eaf-cost): Shared capital and operating cost model for both EAF variants.

```{note}
These models are distinct from the existing LBNL-based EAF models (`NaturalGasEAFPlantPerformanceComponent`, `HydrogenEAFPlantPerformanceComponent`).
The CMU models offer a more detailed energy and mass balance with explicit slag chemistry and are calibrated to the decarbSTEEL v5 dataset.
```

## When to use these models

The CMU EAF models are best suited for systems-level analyses where the steelmaking step needs to reflect realistic feedstock consumption, energy demand, and slag-related material flows.
Common use cases include:

- **Scrap-based steelmaking studies** - evaluating electricity and natural gas demand for a scrap-charged EAF as part of a larger energy system.
- **Renewable steel pathways** - coupling a DRI plant (producing sponge iron from hydrogen or natural gas) with an EAF to assess end-to-end energy, cost, and emissions.
- **Feedstock sensitivity analysis** - varying DRI fraction, pellet grade, scrap composition, or DRI feed temperature to understand impacts on electricity and raw material consumption.
- **Site-level integrated design** - connecting upstream resource models (wind, solar, grid) through electrolyzers and DRI furnaces to the EAF for full-system optimization.

Use the **scrap-only model** when modeling a conventional scrap-recycling EAF.
Use the **DRI model** when the EAF receives sponge iron from an upstream DRI process, with or without supplemental scrap.

## Common concepts

Both models share a core energy and mass balance framework drawn from decarbSTEEL v5. The calculation proceeds in two stages:

1. **Mass balance** - determines slag composition (CaO, MgO, SiO2, Al₂O₃, FeO) from the charged scrap and/or DRI, then computes iron yield, fluxing agent requirements (lime and doloma), and coal injection.
2. **Energy balance** - sums the enthalpies of all input streams (metallic charge, slag formers, oxygen, carbon) and product streams (liquid steel, slag, off-gas CO/CO₂) at the tapping temperature (~1873 K), using reference enthalpy values from decarbSTEEL. The net EAF energy demand is the difference, adjusted for empirical heat losses.

### Feedstock inputs

Both models require upstream feedstocks, each supplied through a `FeedstockPerformanceModel` and connected via a transporter:

| Feedstock | Units | Notes |
|-----------|-------|-------|
| `oxygen` | m³/h | Lancing and combustion |
| `electricity` | kW | Arc energy and auxiliaries |
| `natural_gas` | MMBtu/h | Burner energy |
| `electrodes` | kg/h | Graphite electrode consumption |
| `scrap` | t/h | Steel scrap charge |
| `coal` | t/h | Carbon injection |
| `doloma` | t/h | MgO-bearing flux |
| `lime` | t/h | CaO-bearing flux |
| **DRI only**: `sponge_iron` | t/h | Sponge iron |


(cmu-eaf-scrap-only)=
## Scrap-only EAF performance

To use:

```yaml
performance_model:
  model: CMUElectricArcFurnaceScrapOnlyPerformanceComponent
```

This model represents a conventional EAF charged entirely with scrap steel. The energy and mass balance is computed per tonne of scrap charged, then converted to a per-tonne-liquid-steel (tLS) basis for all output quantities.

Key outputs include consumable rates (oxygen, lime, doloma, coal, electricity per tLS), slag mass and composition, and iron yield from scrap. The heat loss fraction is computed endogenously from the energy balance.

(cmu-eaf-dri)=
## DRI + Scrap EAF performance

To use:

```yaml
performance_model:
  model: CMUElectricArcFurnaceDRIPerformanceComponent
```

This model extends the scrap-only model to handle a mixed charge of **direct reduced iron (sponge iron)** and scrap. It adds an additional `sponge_iron` feedstock input (t/h) and introduces several DRI-specific configuration parameters.

The energy and mass balance is computed per tonne of DRI charged, then converted to a per-tonne-liquid-steel basis. The heat loss adjustment is taken from the scrap-only model via the `EAF_scrap_heat_loss_adjustment_abs` parameter, ensuring thermodynamic consistency between the two model variants.

(cmu-eaf-cost)=
## EAF cost model

To use:

```yaml
cost_model:
  model: CMUElectricArcFurnaceCostModel
```

A shared cost model for both EAF variants, calibrated to decarbSTEEL v5 with costs in **2022 USD**.

### Outputs

- `CapEx` - total capital expenditure ($).
- `OpEx` - annual operating expenditure ($), comprising labor and maintenance costs. Feedstock costs (electricity, natural gas, electrodes, etc.) are handled separately by the upstream `FeedstockCostModel` components.

## Example configurations

Two example configurations are included under `examples/21_iron_examples/iron_cmu/`:

- **`scrap_only/`** - a scrap-charged EAF with all required feedstocks and the `CMUElectricArcFurnaceCostModel`.
- **`dri/`** - a DRI + scrap EAF with an additional sponge iron feedstock, using BF-grade pellets with hot charging.

## References

- CMU decarbSTEEL v5: <https://kilthub.cmu.edu/articles/model/decarbSTEEL_Decarbonizing_Steelmaking_TechnoEconomic_EvaLuation_tool/27119169>
