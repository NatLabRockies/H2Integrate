# H2Integrate: Holistic Hybrids Optimization and Design Tool

[![PyPI version](https://badge.fury.io/py/H2Integrate.svg)](https://badge.fury.io/py/H2Integrate)
![CI Tests](https://github.com/NREL/H2Integrate/actions/workflows/ci.yml/badge.svg)
[![image](https://img.shields.io/pypi/pyversions/H2Integrate.svg)](https://pypi.python.org/pypi/H2Integrate)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![DOI:10.5281/zenodo.17903150](https://zenodo.org/badge/DOI/10.5281/zenodo.17903149.svg)](https://zenodo.org/records/17903149)

[![DOI 10.1088/1742-6596/2767/8/082019](https://img.shields.io/badge/DOI-10.1088%2F1742--6596%2F2767%2F8%2F082019-brightgreen?link=[https://doi.org/10.1088/1742-6596/2767/8/082019](https://doi.org/10.1088/1742-6596/2767/8/082019))](https://iopscience.iop.org/article/10.1088/1742-6596/2767/8/082019/pdf)
[![DOI 10.1088/1742-6596/2767/6/062017](https://img.shields.io/badge/DOI-10.1088%2F1742--6596%2F2767%2F6%2F062017-brightgreen?link=[https://doi.org/10.1088/1742-6596/2767/6/062017](https://doi.org/10.1088/1742-6596/2767/6/062017))](https://iopscience.iop.org/article/10.1088/1742-6596/2767/6/062017/pdf)
[![DOI 10.21203/rs.3.rs-4326648/v1](https://img.shields.io/badge/DOI-10.21203%2Frs.3.rs--4326648%2Fv1-brightgreen?link=[https://doi.org/10.21203/rs.3.rs-4326648/v1](https://doi.org/10.21203/rs.3.rs-4326648/v1))](https://assets-eu.researchsquare.com/files/rs-4326648/v1_covered_338a5071-b74b-4ecd-9d2a-859e8d988b5c.pdf?c=1716199726)

H2Integrate is an open-source Python package for modeling and designing hybrid energy systems producing electricity, hydrogen, ammonia, steel, and other products.

Note: The current version of H2Integrate is under active development and may be missing features that existed previously. H2Integrate v0.2.0 is the last version that uses the prior framework.

## Software Citation

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

## Publications where H2Integrate has been used

For more context about H2Integrate and to see analyses that have been performed using the tool, please see some of these publications.
PDFs are available in the linked titles.

### Nationwide techno-economic analysis of clean hydrogen production powered by a hybrid renewable energy plant for over 50,000 locations in the United States.
The levelized cost of hydrogen is calculated for varying technology costs, and tax credits to
explore cost sensitivities independent of plant design, performance, and site selection. Our
findings suggest that strategies for cost reduction include selecting sites with abundant wind
resources, complementary wind and solar resources, and optimizing the sizing of wind and solar
assets to maximize the hybrid plant capacity factor.

Grant, E., et al. "[Hybrid power plant design for low-carbon hydrogen in the United States.](https://iopscience.iop.org/article/10.1088/1742-6596/2767/8/082019/pdf)" Journal of Physics: Conference Series. Vol. 2767. No. 8. IOP Publishing, 2024.

### Exploring the role of producing low-carbon hydrogen using water electrolysis powered by offshore wind in facilitating the United States’ transition to a net-zero emissions economy by 2050.
Conducting a regional techno-economic analysis at four U.S. coastal sites, the study evaluates two
energy transmission configurations and examines associated costs for the years 2025, 2030, and 2035.
The results highlight that locations using fixed-bottom technology may achieve cost-competitive
water electrolysis hydrogen production by 2030 through leveraging geologic hydrogen storage and
federal policy incentives.

Brunik, K., et al. "[Potential for large-scale deployment of offshore wind-to-hydrogen systems in the United States.](https://iopscience.iop.org/article/10.1088/1742-6596/2767/6/062017/pdf)" Journal of Physics: Conference Series. Vol. 2767. No. 6. IOP Publishing, 2024.

### Examining how tightly-coupled gigawatt-scale wind- and solar-sourced H2 depends on the ability to store and deliver otherwise-curtailed H2 during times of shortages.
Modeling results suggest that the levelized cost of storage is highly spatially heterogeneous, with
minor impact on the cost of H2 in the Midwest, and potentially significant impact in areas with
emerging H2 economies such as Central California and the Southeast. While TOL/MCH may be the
cheapest aboveground bulk storage solution evaluated, upfront capital costs, modest energy
efficiency, reliance on critical materials, and greenhouse gas emissions from heating remain
concerns.

Breunig, Hanna, et al. "[Hydrogen Storage Materials Could Meet Requirements for GW-Scale Seasonal Storage and Green Steel.](https://assets-eu.researchsquare.com/files/rs-4326648/v1_covered_338a5071-b74b-4ecd-9d2a-859e8d988b5c.pdf?c=1716199726)" (2024).

### DOE Hydrogen Program review presentation of H2Integrate
King, J. and Hammond, S. "[Integrated Modeling, TEA, and Reference Design for Renewable Hydrogen to Green Steel and Ammonia - GreenHEART](https://www.hydrogen.energy.gov/docs/hydrogenprogramlibraries/pdfs/review24/sdi001_king_2024_o.pdf?sfvrsn=a800ca84_3)" (2024).

## Software requirements

- Python version 3.11, 3.12 64-bit
- Other versions may still work, but have not been extensively tested at this time

## Installing from Package Repositories

```bash
pip install h2integrate
```

## Installing from Source

### Easiest approach (recommended)

1. Using Git, navigate to a local target directory and clone repository:

    ```bash
    git clone https://github.com/NREL/H2Integrate.git
    ```

2. Navigate to `H2Integrate`

    ```bash
    cd H2Integrate
    ```

3. Create a conda environment and install H2Integrate and all its dependencies

    ```bash
    conda env create -f environment.yml
    ```

4. Install Cbc.
   1. If using a Unix machine (not Windows), install a final dependency

        ```bash
        conda install -y -c conda-forge coin-or-cbc=2.10.8
        ```

    2. Windows users will have to manually install Cbc: https://github.com/coin-or/Cbc

An additional step can be added if additional dependencies are required, or you plan to use this
environment for development work.

- Pass `-e` for an editable developer install
- Use one of the extra flags as needed:
  - `examples`: allows you to use the Jupyter Notebooks
  - `develop`: adds developer and documentation tools
  - `all` simplifies adding all the dependencies

This looks like the following for a developer installation:

```bash
pip install -e ".[all]"
```

### Customizable

1. Using Git, navigate to a local target directory and clone repository:

    ```bash
    git clone https://github.com/NREL/H2Integrate.git
    ```

2. Navigate to `H2Integrate`

    ```bash
    cd H2Integrate
    ```

3. Create a new virtual environment and change to it. Using Conda Python 3.11 (choose your favorite
   supported version) and naming it 'h2integrate' (choose your desired name):

    ```bash
    conda create --name h2integrate python=3.11 -y
    conda activate h2integrate
    ```

4. Install H2Integrate and its dependencies:

    ```bash
    conda install -y -c conda-forge glpk
    ```

    Note: Unix users should install Cbc via:

    ```bash
    conda install -y -c conda-forge coin-or-cbc=2.10.8
    ```

    Windows users will have to manually install Cbc: https://github.com/coin-or/Cbc.

    - If you want to just use H2Integrate:

       ```bash
       pip install .
       ```

    - If you want to work with the examples:

       ```bash
       pip install ".[examples]"
       ```

    - If you also want development dependencies for running tests and building docs:

       ```bash
       pip install -e ".[develop]"
       ```

       Please be sure to also install the pre-commit hooks if contributing code back to the main
       repository via the following. This enables a series of automated formatting and code linting
       (style and correctness checking) to ensure the code is stylistically consistent.

       ```bash
       pre-commit install
       ```

       If a check (or multiple) fails (commit is blocked), and reformatting was done, then restage
       (`git add`) your files and commit them again to see if all issues were resolved without user
       intervention. If changes are required follow the suggested fix, or resolve the stated
       issue(s). Restaging and committing may take multiple attempts steps if errors are unaddressed
       or insufficiently addressed. Please see [pre-commit](https://pre-commit.com/),
       [ruff](https://docs.astral.sh/ruff/), or [isort](https://pycqa.github.io/isort/) for more
       information.

    - In one step, all dependencies can be installed as:

      ```bash
      pip install -e ".[all]"
      ```

5. The functions which download resource data require an NREL API key. Obtain a key from:

    [https://developer.nrel.gov/signup/](https://developer.nrel.gov/signup/)

6. To set up the `NREL_API_KEY` and `NREL_API_EMAIL` required for resource downloads, follow the steps
    outlined in [this doc page](https://h2integrate.readthedocs.io/en/latest/getting_started/environment_variables.html).

7. Verify setup by running tests:

    ```bash
    pytest
    ```

## Getting Started

The [Examples](./examples/) contain Jupyter notebooks and sample YAML files for common usage
scenarios in H2Integrate. These are actively maintained and updated to demonstrate H2Integrate's
capabilities. For full details on simulation options and other features, documentation is
forthcoming.

## Contributing

Interested in improving H2Integrate? Please see the [Contributor's Guide](./docs/CONTRIBUTING.md)
section for more information.
