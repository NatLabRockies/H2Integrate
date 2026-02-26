# Marine Carbon Dioxide Capture Models
Marine carbon dioxide (CO₂) capture technologies aim to remove CO₂ from the ocean or enhance the ocean’s natural capacity to store atmospheric CO₂. These approaches provide additional pathways for managing carbon in the marine environment and can complement land-based strategies for resource management and ocean health.

This section provides an overview of the marine carbon dioxide capture models integrated into H2Integrate. The models are adapted from and maintained in NREL's [MarineCarbonManagement Repository](https://github.com/Nrel/MarineCarbonManagement) and have been integrated here for ease of scenario analysis and system-level optimization.


## Direct Ocean Capture (DOC) Model

Direct Ocean Capture extracts dissolved CO₂ directly from seawater using engineered processes. By reducing the concentration of dissolved inorganic carbon, the ocean naturally reabsorbs an equivalent amount of atmospheric CO₂. The resultant CO₂ can then be used for downstream processes and conversion or storage.

The DOC model is built on electrodialysis-based separation and includes both performance and cost components, allowing users to explore a wide range of system configurations, operational scenarios, and infrastructure options. It is designed for process design, optimization, and cost evaluation of marine carbon capture systems and is integrated from NREL's [MarineCarbonManagement Repository](https://github.com/Nrel/MarineCarbonManagement). Additional information about this specific model can be found in [Niffenegger et al.](https://doi.org/10.3390/cleantechnol7030052)

### Why Use This Model
- Evaluate technology performance — quantify system throughput, process efficiencies, and resource usage under different operating conditions.
- Optimize system sizing — explore trade-offs between flow rates, equipment count, and storage capacity.
- Estimate costs — compute capital and operational expenses for different infrastructure configurations.
- Integrate with other marine systems — assess synergies with energy systems or other ocean-based facilities.

### Model Structure
Like other technology models in H2Integrate, the DOC model contains both a Performance Model and a Cost Model.

#### DOC Performance Model
Simulates the physical and operational aspects of the electrodialysis process.

**Outputs include:**
- Hourly CO₂ capture rate (t/h)
- Annual CO₂ throughput (t/year)
- Total storage tank volume (m³)
- Theoretical maximum plant throughput (t/h)

**Key configuration parameters:**
- Electrodialysis unit power and flow rate
- Separation efficiencies
- Seawater properties (temperature, salinity, dissolved inorganic carbon, pH)
- Storage tank capacity and operational constraints

#### DOC Cost Model
Estimates the capital expenditure (CapEx) and annual operating expenditure (OpEx) for a given system configuration.

**Cost inputs include:**
- Total storage tank volume
- Maximum plant throughput
- Infrastructure type (desal, swCool, or new)
- Annual throughput (t/year)

**Outputs include:**
- Initial capital cost (USD)
- Annual operational cost (USD/year)


## Ocean Alkalinity Enhancement (OAE) Model
The Ocean Alkalinity Enhancement (OAE) Model simulates the process of increasing seawater alkalinity through the addition of alkaline substances. This change in water chemistry enhances the ocean’s natural ability to absorb and hold dissolved carbon.

```{note}
This model estimates the CO₂ absorption potential of the ocean after the OAE process. CO₂ is not a usable downstream product.
```

The OAE model is adapted from NREL’s MarineCarbonManagement Repository and includes both performance and cost components, as well as a financial model enabling users to explore a variety of system designs, operational strategies, and infrastructure setups. Additional information about this specific model can be found in [Niffenegger et al.](https://doi.org/10.3390/cleantechnol8010012)

### Why Use This Model
- Assess system performance — determine processing capacity, flow characteristics, and operational profiles.
- Test operational strategies — evaluate dosing rates, storage requirements, and acid handling methods.
- Estimate costs — calculate capital and operating costs for different plant scales and configurations.
- Explore co-benefits — evaluate potential for producing marketable products such as mineral byproducts.

### Model Structure
The OAE model contains both a Performance Model and a Cost Model, with an additional Cost and Financial Model for extended economic analysis.

#### OAE Performance Model
Simulates the alkalinity enhancement process, tracking physical, chemical, and operational parameters.

**Outputs include:**
- Hourly and annual dissolved carbon processing (t/h, t/year)
- Flow rate, pH, alkalinity, dissolved inorganic carbon, salinity, and temperature of treated seawater
- Mass and value of co-products (e.g., acid, recovered carbonate aggregate)
- Acid handling volumes and disposal costs

**Key configuration parameters:**
- Alkalinity addition rate and flow fractions
- Electrodialysis system capacity
- Seawater temperature, salinity, and carbonate chemistry
- Acid disposal method and storage capacity

#### OAE Cost Model
Computes capital (CapEx) and operational (OpEx) costs based on plant design and operating profile.

**Inputs include:**
- Product mass and value
- Acid disposal volumes and costs
- Maximum processing capacity
- Byproduct and slurry production rates

**Outputs include:**
- Initial capital cost (USD)
- Annual operating cost (USD/year)

#### OAE Cost and Financial Model
Extends the cost model to include financial metrics. Allows calculation of net present value (NPV) and determination of credit values required for financial viability.

**Additional inputs include:**
- Levelized cost of electricity (LCOE)
- Annual energy consumption
- Operational cost details from the performance model

**Outputs include:**
- Net Present Value (USD)
- Required credit value (USD per tonne processed carbon)
