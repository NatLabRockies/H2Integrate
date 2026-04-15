# H2Integrate: Holistic Hybrids Optimization and Design Tool

[![PyPI version](https://badge.fury.io/py/H2Integrate.svg)](https://badge.fury.io/py/H2Integrate)
![CI Tests](https://github.com/NatLabRockies/H2Integrate/actions/workflows/ci.yml/badge.svg)
[![image](https://img.shields.io/pypi/pyversions/H2Integrate.svg)](https://pypi.python.org/pypi/H2Integrate)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![DOI 10.5281/zenodo.17903150](https://zenodo.org/badge/DOI/10.5281/zenodo.17903150.svg)](https://zenodo.org/records/17903150)

H2Integrate (H2I) is an open-source Python package for hybrid energy systems engineering design and technoeconomic analysis.
It models hybrid energy plants that produce electricity, hydrogen, ammonia, steel, and other products to perform optimization and scenario analysis.

## Installation

The recommended installation method is via pip from PyPI, which will install the latest stable release of H2Integrate and its dependencies:

```bash
pip install h2integrate
```

For installing from source, development setup, and additional installation options, see the [full installation instructions](https://h2integrate.readthedocs.io/en/latest/getting_started/install.html).

## What H2Integrate Does

H2Integrate is both a **hybrid systems engineering design tool** and a **technoeconomic analysis (TEA) tool**. It significantly expands beyond generalized tools by offering:

- **Detailed equipment-level modeling** with a wide range of subsystem variation options
- **High-resolution, location-specific resource data** for site-dependent performance modeling
- **Cost inputs settable by the user** with examples based on the Annual Technology Baseline (ATB)
- **Optimization and scenario analysis** to explore design trade-offs across hybrid plant configurations

### Available Technologies

H2I includes models for a broad set of energy generation, conversion, and storage technologies:

- **Renewable generation**: land-based wind, offshore wind, solar PV, wave, tidal
- **Conventional generation**: natural gas combined cycle (NGCC), natural gas combustion turbines (NGCT), grid electricity
- **Hydrogen production**: PEM electrolysis, NG-SMR
- **Energy storage**: Li-ion batteries, long-duration energy storage (LDES), pumped storage hydropower (PSH)
- **Fuel cells**: H2 PEM fuel cells
- **Industrial processes**: ammonia synthesis, iron ore reduction, steel production, and more

## Getting Started

See the [Getting Started guide](https://h2integrate.readthedocs.io/en/latest/intro.html) for an introduction to H2Integrate.
The [Examples folder](./examples/) contain Jupyter notebooks and sample YAML files for common usage scenarios.

## Publications

For more context about H2Integrate and analyses performed using the tool, see the publications below.
PDFs are available in the linked titles.
Note: H2Integrate was previously known as GreenHEART, and some publications may refer to it by that name.

### Nationwide techno-economic analysis of clean hydrogen production powered by a hybrid renewable energy plant for over 50,000 locations in the United States

The levelized cost of hydrogen is calculated for varying technology costs, and tax credits to
explore cost sensitivities independent of plant design, performance, and site selection. Our
findings suggest that strategies for cost reduction include selecting sites with abundant wind
resources, complementary wind and solar resources, and optimizing the sizing of wind and solar
assets to maximize the hybrid plant capacity factor.

Grant, E., et al. "[Hybrid power plant design for low-carbon hydrogen in the United States.](https://iopscience.iop.org/article/10.1088/1742-6596/2767/8/082019/pdf)" Journal of Physics: Conference Series. Vol. 2767. No. 8. IOP Publishing, 2024.

### Exploring the role of producing low-carbon hydrogen using water electrolysis powered by offshore wind in facilitating the United States' transition to a net-zero emissions economy by 2050

Conducting a regional techno-economic analysis at four U.S. coastal sites, the study evaluates two
energy transmission configurations and examines associated costs for the years 2025, 2030, and 2035.
The results highlight that locations using fixed-bottom technology may achieve cost-competitive
water electrolysis hydrogen production by 2030 through leveraging geologic hydrogen storage and
federal policy incentives.

Brunik, K., et al. "[Potential for large-scale deployment of offshore wind-to-hydrogen systems in the United States.](https://iopscience.iop.org/article/10.1088/1742-6596/2767/6/062017/pdf)" Journal of Physics: Conference Series. Vol. 2767. No. 6. IOP Publishing, 2024.

### Examining how tightly-coupled gigawatt-scale wind- and solar-sourced H2 depends on the ability to store and deliver otherwise-curtailed H2 during times of shortages

Modeling results suggest that the levelized cost of storage is highly spatially heterogeneous, with
minor impact on the cost of H2 in the Midwest, and potentially significant impact in areas with
emerging H2 economies such as Central California and the Southeast. While TOL/MCH may be the
cheapest aboveground bulk storage solution evaluated, upfront capital costs, modest energy
efficiency, reliance on critical materials, and greenhouse gas emissions from heating remain
concerns.

Breunig, Hanna, et al. "[Hydrogen Storage Materials Could Meet Requirements for GW-Scale Seasonal Storage and Green Steel.](https://assets-eu.researchsquare.com/files/rs-4326648/v1_covered_338a5071-b74b-4ecd-9d2a-859e8d988b5c.pdf?c=1716199726)" (2024).

### DOE Hydrogen Program review presentation of H2Integrate

King, J. and Hammond, S. "[Integrated Modeling, TEA, and Reference Design for Renewable Hydrogen to Green Steel and Ammonia - GreenHEART](https://www.hydrogen.energy.gov/docs/hydrogenprogramlibraries/pdfs/review24/sdi001_king_2024_o.pdf?sfvrsn=a800ca84_3)" (2024).

## Software Citation

If you use H2I or any of its components in your work, please cite this in your publications using the following BibTeX:

```bibtex
@software{brunik_2025_17903150,
  author = {Brunik, Kaitlin and
    Grant, Elenya and
    Thomas, Jared and
    Starke, Genevieve M and
    Martin, Jonathan and
    Ramos, Dakota and
    Koleva, Mariya and
    Reznicek, Evan and
    Hammond, Rob and
    Stanislawski, Brooke and
    Kiefer, Charlie and
    Irmas, Cameron and
    Vijayshankar, Sanjana and
    Riccobono, Nicholas and
    Frontin, Cory and
    Clark, Caitlyn and
    Barker, Aaron and
    Gupta, Abhineet and
    Kee, Benjamin (Jamie) and
    King, Jennifer and
    Jasa, John and
    Bay, Christopher},
  title = {H2Integrate: Holistic Hybrids Optimization and Design Tool},
  month = dec,
  year = 2025,
  publisher = {Zenodo},
  version = {0.4.0},
  doi = {10.5281/zenodo.17903150},
  url = {https://doi.org/10.5281/zenodo.17903150},
}
```

## Contributing

Interested in improving H2Integrate? Please see the [Contributor's Guide](./docs/CONTRIBUTING.md) for more information.
