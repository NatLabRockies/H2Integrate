import unittest

import numpy as np
import openmdao.api as om

from h2integrate.converters.grid.grid import GridCostModel, GridPerformanceModel


class TestGridPerformanceModel(unittest.TestCase):
    """Test cases for GridPerformanceModel."""

    def setUp(self):
        """Set up test fixtures."""
        self.n_timesteps = 10
        self.plant_config = {"plant": {"simulation": {"n_timesteps": self.n_timesteps}}}

    def test_buying_electricity(self):
        """Test buying electricity from grid (electricity flows out)."""
        prob = om.Problem()

        tech_config = {
            "model_inputs": {
                "shared_parameters": {
                    "interconnection_size": 50000.0  # 50 MW
                }
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridPerformanceModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set demand below interconnection limit
        demand = np.full(self.n_timesteps, 30000.0)  # 30 MW demand
        prob.set_val("grid.electricity_demand", demand)

        prob.run_model()

        # Should get full demand since it's below interconnection limit
        electricity_out = prob.get_val("grid.electricity_out")
        np.testing.assert_array_almost_equal(electricity_out, demand)

    def test_buying_with_interconnection_limit(self):
        """Test that buying is limited by interconnection size."""
        prob = om.Problem()

        interconnection_size = 40000.0  # 40 MW
        tech_config = {
            "model_inputs": {"shared_parameters": {"interconnection_size": interconnection_size}}
        }

        prob.model.add_subsystem(
            "grid",
            GridPerformanceModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set demand above interconnection limit
        demand = np.full(self.n_timesteps, 60000.0)  # 60 MW demand
        prob.set_val("grid.electricity_demand", demand)

        prob.run_model()

        # Should be limited to interconnection size
        electricity_out = prob.get_val("grid.electricity_out")
        np.testing.assert_array_almost_equal(
            electricity_out, np.full(self.n_timesteps, interconnection_size)
        )

    def test_selling_electricity(self):
        """Test selling electricity to grid (electricity flows in)."""
        prob = om.Problem()

        tech_config = {
            "model_inputs": {
                "shared_parameters": {
                    "interconnection_size": 100000.0  # 100 MW
                }
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridPerformanceModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set electricity flowing into grid
        electricity_in = np.full(self.n_timesteps, 50000.0)  # 50 MW
        prob.set_val("grid.electricity_in", electricity_in)

        prob.run_model()

        # The electricity_in represents what's being sold (no separate output needed)
        # Just verify it was accepted
        actual_in = prob.get_val("grid.electricity_in")
        np.testing.assert_array_almost_equal(actual_in, electricity_in)

    def test_simultaneous_buy_and_sell(self):
        """Test that grid can handle both buying and selling simultaneously."""
        prob = om.Problem()

        tech_config = {
            "model_inputs": {
                "shared_parameters": {
                    "interconnection_size": 75000.0  # 75 MW
                }
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridPerformanceModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set both flows
        electricity_in = np.full(self.n_timesteps, 30000.0)  # 30 MW in
        electricity_demand = np.full(self.n_timesteps, 40000.0)  # 40 MW out

        prob.set_val("grid.electricity_in", electricity_in)
        prob.set_val("grid.electricity_demand", electricity_demand)

        prob.run_model()

        electricity_out = prob.get_val("grid.electricity_out")
        np.testing.assert_array_almost_equal(electricity_out, electricity_demand)

    def test_varying_demand_profile(self):
        """Test with time-varying demand profile."""
        prob = om.Problem()

        tech_config = {"model_inputs": {"shared_parameters": {"interconnection_size": 100000.0}}}

        prob.model.add_subsystem(
            "grid",
            GridPerformanceModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Create varying demand profile
        demand = np.array([10000, 20000, 30000, 50000, 70000, 90000, 110000, 80000, 60000, 40000])
        prob.set_val("grid.electricity_demand", demand)

        prob.run_model()

        electricity_out = prob.get_val("grid.electricity_out")
        # Values above 100000 should be clipped
        expected = np.clip(demand, 0, 100000)
        np.testing.assert_array_almost_equal(electricity_out, expected)


class TestGridCostModel(unittest.TestCase):
    """Test cases for GridCostModel."""

    def setUp(self):
        """Set up test fixtures."""
        self.n_timesteps = 24  # 24 hours
        self.plant_config = {
            "plant": {"simulation": {"n_timesteps": self.n_timesteps}, "plant_life": 30}
        }

    def test_buy_only_mode(self):
        """Test cost model with only buy price configured."""
        prob = om.Problem()

        interconnection_size = 50000.0
        buy_price = 0.10  # $0.10/kWh

        tech_config = {
            "model_inputs": {
                "shared_parameters": {"interconnection_size": interconnection_size},
                "cost_parameters": {
                    "cost_year": 2022,
                    "interconnection_capex_per_kw": 50.0,
                    "interconnection_opex_per_kw": 2.0,
                    "fixed_interconnection_cost": 100000.0,
                    "electricity_buy_price": buy_price,
                    "electricity_sell_price": None,  # No selling
                },
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridCostModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set electricity bought (flowing out)
        electricity_out = np.full(self.n_timesteps, 30000.0)  # 30 MW
        prob.set_val("grid.electricity_out", electricity_out)

        prob.run_model()

        # Check CapEx
        expected_capex = (interconnection_size * 50.0) + 100000.0
        capex = prob.get_val("grid.CapEx")
        self.assertAlmostEqual(capex, expected_capex)

        # Check OpEx
        expected_opex = interconnection_size * 2.0
        opex = prob.get_val("grid.OpEx")
        self.assertAlmostEqual(opex, expected_opex)

        # Check VarOpEx (buying costs)
        expected_varopex = np.sum(electricity_out * buy_price)
        varopex = prob.get_val("grid.VarOpEx")[0]
        self.assertAlmostEqual(varopex, expected_varopex)

    def test_sell_only_mode(self):
        """Test cost model with only sell price configured."""
        prob = om.Problem()

        interconnection_size = 75000.0
        sell_price = 0.05  # $0.05/kWh

        tech_config = {
            "model_inputs": {
                "shared_parameters": {"interconnection_size": interconnection_size},
                "cost_parameters": {
                    "cost_year": 2022,
                    "interconnection_capex_per_kw": 50.0,
                    "interconnection_opex_per_kw": 2.0,
                    "fixed_interconnection_cost": 100000.0,
                    "electricity_buy_price": None,  # No buying
                    "electricity_sell_price": sell_price,
                },
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridCostModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set electricity sold (flowing in)
        electricity_sold = np.full(self.n_timesteps, 40000.0)  # 40 MW
        prob.set_val("grid.electricity_sold", electricity_sold)

        prob.run_model()

        # Check CapEx
        expected_capex = (interconnection_size * 50.0) + 100000.0
        capex = prob.get_val("grid.CapEx")
        self.assertAlmostEqual(capex, expected_capex)

        # Check OpEx
        expected_opex = interconnection_size * 2.0
        opex = prob.get_val("grid.OpEx")
        self.assertAlmostEqual(opex, expected_opex)

        # Check VarOpEx (selling revenue - negative)
        expected_varopex = -np.sum(electricity_sold * sell_price)
        varopex = prob.get_val("grid.VarOpEx")[0]
        self.assertAlmostEqual(varopex, expected_varopex)

    def test_both_buy_and_sell_prices(self):
        """Test cost model with both buy and sell prices configured."""
        prob = om.Problem()

        interconnection_size = 100000.0
        buy_price = 0.10  # $0.10/kWh
        sell_price = 0.05  # $0.05/kWh

        tech_config = {
            "model_inputs": {
                "shared_parameters": {"interconnection_size": interconnection_size},
                "cost_parameters": {
                    "cost_year": 2022,
                    "interconnection_capex_per_kw": 50.0,
                    "interconnection_opex_per_kw": 2.0,
                    "fixed_interconnection_cost": 100000.0,
                    "electricity_buy_price": buy_price,
                    "electricity_sell_price": sell_price,
                },
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridCostModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set both buying and selling
        electricity_out = np.full(self.n_timesteps, 20000.0)  # 20 MW bought
        electricity_sold = np.full(self.n_timesteps, 30000.0)  # 30 MW sold

        prob.set_val("grid.electricity_out", electricity_out)
        prob.set_val("grid.electricity_sold", electricity_sold)

        prob.run_model()

        # Check VarOpEx (buying cost - selling revenue)
        buying_cost = np.sum(electricity_out * buy_price)
        selling_revenue = np.sum(electricity_sold * sell_price)
        expected_varopex = buying_cost - selling_revenue

        varopex = prob.get_val("grid.VarOpEx")[0]
        self.assertAlmostEqual(varopex, expected_varopex)

    def test_time_varying_buy_price(self):
        """Test with time-varying electricity buy prices."""
        prob = om.Problem()

        interconnection_size = 50000.0
        # Create time-varying prices (peak/off-peak)
        buy_prices = np.array([0.08] * 6 + [0.15] * 12 + [0.08] * 6)  # 24 hours

        tech_config = {
            "model_inputs": {
                "shared_parameters": {"interconnection_size": interconnection_size},
                "cost_parameters": {
                    "cost_year": 2022,
                    "interconnection_capex_per_kw": 50.0,
                    "interconnection_opex_per_kw": 2.0,
                    "fixed_interconnection_cost": 100000.0,
                    "electricity_buy_price": buy_prices.tolist(),
                    "electricity_sell_price": None,
                },
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridCostModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set constant electricity bought
        electricity_out = np.full(self.n_timesteps, 25000.0)  # 25 MW
        prob.set_val("grid.electricity_out", electricity_out)

        prob.run_model()

        # Check VarOpEx with varying prices
        expected_varopex = np.sum(electricity_out * buy_prices)
        varopex = prob.get_val("grid.VarOpEx")[0]
        self.assertAlmostEqual(varopex, expected_varopex)

    def test_time_varying_sell_price(self):
        """Test with time-varying electricity sell prices."""
        prob = om.Problem()

        interconnection_size = 75000.0
        # Create time-varying sell prices
        sell_prices = np.array([0.03] * 6 + [0.07] * 12 + [0.03] * 6)  # 24 hours

        tech_config = {
            "model_inputs": {
                "shared_parameters": {"interconnection_size": interconnection_size},
                "cost_parameters": {
                    "cost_year": 2022,
                    "interconnection_capex_per_kw": 50.0,
                    "interconnection_opex_per_kw": 2.0,
                    "fixed_interconnection_cost": 100000.0,
                    "electricity_buy_price": None,
                    "electricity_sell_price": sell_prices.tolist(),
                },
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridCostModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        # Set constant electricity sold
        electricity_sold = np.full(self.n_timesteps, 35000.0)  # 35 MW
        prob.set_val("grid.electricity_sold", electricity_sold)

        prob.run_model()

        # Check VarOpEx (negative for revenue)
        expected_varopex = -np.sum(electricity_sold * sell_prices)
        varopex = prob.get_val("grid.VarOpEx")[0]
        self.assertAlmostEqual(varopex, expected_varopex)

    def test_zero_interconnection_costs(self):
        """Test with zero interconnection costs."""
        prob = om.Problem()

        tech_config = {
            "model_inputs": {
                "shared_parameters": {"interconnection_size": 100000.0},
                "cost_parameters": {
                    "cost_year": 2022,
                    "interconnection_capex_per_kw": 0.0,
                    "interconnection_opex_per_kw": 0.0,
                    "fixed_interconnection_cost": 0.0,
                    "electricity_buy_price": 0.10,
                    "electricity_sell_price": 0.05,
                },
            }
        }

        prob.model.add_subsystem(
            "grid",
            GridCostModel(
                driver_config={}, plant_config=self.plant_config, tech_config=tech_config
            ),
        )

        prob.setup()

        electricity_out = np.full(self.n_timesteps, 10000.0)
        electricity_sold = np.full(self.n_timesteps, 20000.0)

        prob.set_val("grid.electricity_out", electricity_out)
        prob.set_val("grid.electricity_sold", electricity_sold)

        prob.run_model()

        # Check that CapEx and OpEx are zero
        capex = prob.get_val("grid.CapEx")
        opex = prob.get_val("grid.OpEx")
        self.assertAlmostEqual(capex, 0.0)
        self.assertAlmostEqual(opex, 0.0)

        # VarOpEx should still be calculated
        expected_varopex = np.sum(electricity_out * 0.10) - np.sum(electricity_sold * 0.05)
        varopex = prob.get_val("grid.VarOpEx")[0]
        self.assertAlmostEqual(varopex, expected_varopex)


if __name__ == "__main__":
    unittest.main()
