import pytest
import openmdao.api as om
from openmdao.core.driver import Driver

from h2integrate.core.pose_optimization import PoseOptimization


DESIGN_VARIABLES = {
    "solar": {"system_capacity_DC": {"flag": True}},
    "electrolyzer": {"n_clusters": {"flag": True}},
}


def make_config(driver):
    return {
        "general": {"folder_output": "outputs"},
        "driver": driver,
        "design_variables": DESIGN_VARIABLES,
    }


def set_driver(driver):
    return PoseOptimization(make_config(driver)).set_driver(om.Problem())


@pytest.fixture
def csv_cases(tmp_path):
    csv_fpath = tmp_path / "cases.csv"
    csv_fpath.write_text("solar.system_capacity_DC,electrolyzer.n_clusters\n25000.0,5.0\n")
    return csv_fpath


@pytest.mark.unit
@pytest.mark.parametrize(
    "generator_options,generator_class",
    [
        ({"generator": "uniform", "num_samples": 5, "seed": 1}, om.UniformGenerator),
        ({"generator": "fullfact", "levels": 3}, om.FullFactorialGenerator),
        ({"generator": "plackettburman"}, om.PlackettBurmanGenerator),
        ({"generator": "boxbehnken"}, om.BoxBehnkenGenerator),
        (
            {"generator": "latinhypercube", "num_samples": 5, "criterion": "center", "seed": 1},
            om.LatinHypercubeGenerator,
        ),
    ],
    ids=["uniform", "fullfact", "plackettburman", "boxbehnken", "latinhypercube"],
)
def test_parameter_sweep_generators(generator_options, generator_class):
    sweep_options = {"flag": True, "debug_print": False} | generator_options
    prob = set_driver({"parameter_sweep": sweep_options})

    assert isinstance(prob.driver, om.DOEDriver)
    assert isinstance(prob.driver.options["generator"], generator_class)


@pytest.mark.unit
def test_parameter_sweep_options(subtests, csv_cases):
    sweep_options = {
        "flag": True,
        "generator": "csvgen",
        "filename": str(csv_cases),
        "debug_print": True,
        "run_parallel": False,
    }

    with subtests.test("CSV generator with a valid file"):
        prob = set_driver({"parameter_sweep": sweep_options})
        assert isinstance(prob.driver.options["generator"], om.CSVGenerator)

    with subtests.test("Debug print and run parallel options"):
        assert "desvars" in prob.driver.options["debug_print"]
        assert prob.driver.options["run_parallel"] is False

    with subtests.test("Legacy design_of_experiments key"):
        prob = set_driver({"design_of_experiments": sweep_options})
        assert isinstance(prob.driver.options["generator"], om.CSVGenerator)


@pytest.mark.unit
def test_parameter_sweep_errors(subtests, tmp_path):
    with subtests.test("CSV file with formatting issues"):
        csv_fpath = tmp_path / "bad_cases.csv"
        csv_fpath.write_bytes(
            b"\xef\xbb\xbfsolar.system_capacity_DC,electrolyzer.n_clusters\n25000.0,5.0\n"
        )
        sweep_options = {
            "flag": True,
            "generator": "csvgen",
            "filename": str(csv_fpath),
            "debug_print": False,
        }
        with pytest.raises(UserWarning, match="There may be issues with the csv file"):
            set_driver({"parameter_sweep": sweep_options})

    with subtests.test("Unsupported generator"):
        sweep_options = {"flag": True, "generator": "random", "debug_print": False}
        with pytest.raises(Exception, match="The generator type random is unsupported"):
            set_driver({"parameter_sweep": sweep_options})


@pytest.mark.unit
def test_scipy_optimization_driver(subtests):
    optimization = {
        "flag": True,
        "solver": "COBYLA",
        "step_size": 1.0e-4,
        "tol": 1.0e-5,
        "max_iter": 50,
        "rhobeg": 2.0,
        "debug_print": True,
    }
    prob = set_driver({"optimization": optimization})

    with subtests.test("Driver and optimizer"):
        assert isinstance(prob.driver, om.ScipyOptimizeDriver)
        assert prob.driver.options["optimizer"] == "COBYLA"

    with subtests.test("Driver options, including renamed keys"):
        assert prob.driver.options["tol"] == pytest.approx(1.0e-5)
        assert prob.driver.options["maxiter"] == 50
        assert prob.driver.opt_settings["rhobeg"] == pytest.approx(2.0)

    with subtests.test("Debug print includes totals for optimization"):
        assert "totals" in prob.driver.options["debug_print"]


@pytest.mark.unit
def test_optimization_driver_defaults_and_errors(subtests):
    with subtests.test("Missing step size warns and uses the default"):
        optimization = {"flag": True, "solver": "SLSQP", "debug_print": False}
        with pytest.warns(UserWarning, match="Step size was not specified"):
            prob = set_driver({"optimization": optimization})
        assert isinstance(prob.driver, om.ScipyOptimizeDriver)

    with subtests.test("Genetic algorithm driver"):
        optimization = {
            "flag": True,
            "solver": "GA",
            "step_size": 1.0e-4,
            "max_gen": 5,
            "pop_size": 4,
            "debug_print": False,
        }
        prob = set_driver({"optimization": optimization})
        assert isinstance(prob.driver, om.SimpleGADriver)
        assert prob.driver.options["max_gen"] == 5
        assert prob.driver.options["pop_size"] == 4

    with subtests.test("Unsupported optimizer"):
        optimization = {"flag": True, "solver": "BFGS", "step_size": 1.0e-4}
        with pytest.raises(ValueError, match="Optimizer BFGS is not yet supported"):
            set_driver({"optimization": optimization})


@pytest.mark.unit
def test_no_driver_selected_warns():
    with pytest.warns(UserWarning, match="no driver is selected"):
        prob = set_driver({})

    assert type(prob.driver) is Driver
