# H2Integrate: Holistic Hybrids Optimization and Design Tool

[![PyPI version](https://badge.fury.io/py/H2Integrate.svg)](https://badge.fury.io/py/H2Integrate)
![CI Tests](https://github.com/NatLabRockies/H2Integrate/actions/workflows/ci.yml/badge.svg)
[![image](https://img.shields.io/pypi/pyversions/H2Integrate.svg)](https://pypi.python.org/pypi/H2Integrate)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![DOI 10.5281/zenodo.17903150](https://zenodo.org/badge/DOI/10.5281/zenodo.17903150.svg)](https://zenodo.org/records/17903150)

H2Integrate (H2I) is an open-source Python package for hybrid energy systems engineering design and technoeconomic analysis.
It models hybrid systems, especially hybrid energy plants that produce electricity, hydrogen, ammonia, steel, and other products, to perform optimization and scenario analysis.

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
- **Cost inputs settable by the user** with examples based on the [Annual Technology Baseline (ATB)](https://atb.nlr.gov/)
- **Optimization and scenario analysis** to explore design trade-offs across hybrid plant configurations

### Available Technologies

H2I includes models for a broad set of energy generation, conversion, and storage technologies.
This is a non-exhaustive list, and the library of available technologies is actively expanding:

- **Electricity generation**: solar PV, wind, wave, tidal, natural gas combined cycle (NGCC), natural gas combustion turbines (NGCT), nuclear, grid
- **Hydrogen production**: PEM electrolysis, NG-SMR
- **Energy storage**: Li-ion batteries, long-duration energy storage (LDES), pumped storage hydropower (PSH)
- **Fuel cells**: H2 PEM fuel cells
- **Industrial processes**: ammonia synthesis, iron ore reduction, steel production, and more

## Getting Started

See the [Getting Started guide](https://h2integrate.readthedocs.io/en/latest/intro.html) for an introduction to H2Integrate.
The [Examples folder](./examples/) contain Jupyter notebooks, Python scripts, and sample YAML files for common usage scenarios.

## Publications

For a full list of publications, see the [Publications section in the documentation](https://h2integrate.readthedocs.io/en/latest/intro.html#publications).
Note: H2Integrate was previously known as GreenHEART, and some publications may refer to it by that name.

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
