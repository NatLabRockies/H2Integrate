# Installing H2Integrate

## Install H2Integrate via PyPI

If you just want to use H2Integrate and aren't developing new models, you can install it from PyPI using pip:

```bash
pip install h2integrate
```

## Installing from Source

If you want to develop new models or contribute to H2Integrate, you can install it from source.

### NREL Resource Data

1. The functions which download resource data require an NREL API key. Obtain a key from:

    [https://developer.nrel.gov/signup/](https://developer.nrel.gov/signup/)

2. To set up the `NREL_API_KEY` and `NREL_API_EMAIL` required for resource downloads, you can create
   Environment Variables called `NREL_API_KEY` and `NREL_API_EMAIL`. Otherwise, you can keep the key
   in a new file called ".env" in the root directory of this project.

    Create a file ".env" that contains the single line:

    ```bash
    NREL_API_KEY=key
    NREL_API_EMAIL=your.name@email.com
    ```

### NREL-Provided Conda Environment Specification (recommended)

1. Using Git, navigate to a local target directory and clone repository:

    ```bash
    git clone https://github.com/NREL/H2Integrate.git
    ```

2. Navigate to `H2Integrate`

    ```bash
    cd H2Integrate
    ```

3. (Optional) If using NREL resource data, you will need an NREL API key, which can be obtained from:
    [https://developer.nrel.gov/signup/](https://developer.nrel.gov/signup/)

    1. In `environment.yml`, add the following lines to the bottom of the file, and replace the
       items in angle brackets (`<>`), including the brackets with your information. Be sure that
       "variables" has no leading spaces

        ```yaml
        variables:
          NREL_API_KEY=<API-KEY>
          NREL_API_EMAIL=<email-address>
        ```

4. Create a conda environment and install H2Integrate and all its dependencies. Please read the
   following two notes about modified installation steps.

    1. If on a Unix machine, uncomment line 8 in `environment.yml` to install Cbc. Windows
      users will need to manually install from <https://github.com/coin-or/Cbc>.
    2. If you plan to use Ard, please uncomment line 9 in `environment.yml` to ensure WISDEM (an Ard
      dependency) is installed from conda to avoid installation issues with some systems.

    ```bash
    conda env create -f environment.yml
    ```

An additional step can be added if additional dependencies are required, or you plan to use this
environment for development work.

- Pass `-e` for an editable developer install
- Use one of the extra flags as needed:
  - `gis`: adds the iron mapping tools.
  - `ard`: adds the Ard-based wind models.
  - `develop`: adds developer and documentation tools, plus optional analysis modifiers `gis` and `ard`.
  - `examples`: allows you to use the Jupyter Notebooks and all examples (includes `ard` and `gis`).
  - `all` simplifies adding all the dependencies.

This looks like the following for a developer installation:

```bash
pip install -e ".[all]"
```

### Manual steps

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

    ````{note}
    Unix users should install Cbc via:

    ```bash
    conda install -y -c conda-forge coin-or-cbc=2.10.8
    ```

    Windows users should install Cbc manually according to https://github.com/coin-or/Cbc.
    ````

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

    - In one step, all dependencies can be installed as:

      ```bash
      pip install -e ".[all]"
      ```

## Developer Notes

Developers should add install using `pip install -e ".[all]"` to ensure documentation testing, and
linting can be done without any additional installation steps.

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
