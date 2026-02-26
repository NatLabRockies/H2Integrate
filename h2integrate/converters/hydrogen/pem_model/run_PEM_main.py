import time
import warnings

import numpy as np
import pandas as pd
from pyomo.environ import *  # FIXME: no * imports, delete whole comment when fixed # noqa: F403

from h2integrate.converters.hydrogen.pem_model.PEM_H2_LT_electrolyzer_Clusters import (
    PEM_H2_Clusters as PEMClusters,
)


# from PyOMO import ipOpt !! FOR SANJANA!!
warnings.filterwarnings("ignore", category=RuntimeWarning)
"""
Perform a LCOH analysis for an offshore wind + Hydrogen PEM system

1. Offshore wind site locations and cost details (4 sites, $1300/kw capex + BOS cost which will come
   from Orbit Runs)~
2. Cost Scaling Based on Year (Have Weiser et. al report with cost scaling for fixed and floating
   tech, will implement)
3. Cost Scaling Based on Plant Size (Shields et. Al report)
4. Future Model Development Required:
- Floating Electrolyzer Platform
"""


#
# ---------------------------
#
class run_PEM_clusters:
    """Inputs:
    `electrical_power_signal`: plant power signal in kWh
    `system_size_mw`: total installed electrolyzer capacity (for green steel this is 1000 MW)
    `num_clusters`: number of PEM clusters that can be run independently
    ->ESG note: I have been using num_clusters = 8 for centralized cases
    Nomenclature:
    `cluster`: cluster is built up of 1MW stacks
    `stack`: must be 1MW (because of current PEM model)
    """

    def __init__(
        self,
        electrical_power_signal,
        system_size_mw,
        num_clusters,
        electrolyzer_direct_cost_kw,
        useful_life,
        user_defined_electrolyzer_params,
        verbose=True,
    ):
        # nomen
        self.cluster_cap_mw = np.round(system_size_mw / num_clusters)
        # capacity of each cluster, must be a multiple of 1 MW

        self.num_clusters = num_clusters
        self.user_params = user_defined_electrolyzer_params
        self.plant_life_yrs = useful_life
        # Do not modify stack_rating_kw or stack_min_power_kw
        # these represent the hard-coded and unmodifiable
        # PEM model basecode
        turndown_ratio = user_defined_electrolyzer_params["turndown_ratio"]
        self.stack_rating_kw = 1000  # single stack rating - DO NOT CHANGE
        self.stack_min_power_kw = turndown_ratio * self.stack_rating_kw
        # self.stack_min_power_kw = 0.1 * self.stack_rating_kw
        self.input_power_kw = electrical_power_signal
        self.cluster_min_power = self.stack_min_power_kw * self.cluster_cap_mw
        self.cluster_max_power = self.stack_rating_kw * self.cluster_cap_mw

        # For the optimization problem:
        self.T = len(self.input_power_kw)
        self.farm_power = 1e9
        self.switching_cost = (
            (electrolyzer_direct_cost_kw * 0.15 * self.cluster_cap_mw * 1000)
            * (1.48e-4)
            / (0.26586)
        )
        self.verbose = verbose

    def run_grid_connected_pem(self, system_size_mw, hydrogen_production_capacity_required_kgphr):
        pem = PEMClusters(
            system_size_mw,
            self.plant_life_yrs,
            **self.user_params,
        )

        power_timeseries, stack_current = pem.grid_connected_func(
            hydrogen_production_capacity_required_kgphr
        )
        h2_ts, h2_tot = pem.run_grid_connected_workaround(power_timeseries, stack_current)
        # h2_ts, h2_tot = pem.run(power_timeseries)
        h2_df_ts = pd.Series(h2_ts, name="Cluster #0")
        h2_df_tot = pd.Series(h2_tot, name="Cluster #0")
        # h2_df_ts = pd.DataFrame(h2_ts, index=list(h2_ts.keys()), columns=['Cluster #0'])
        # h2_df_tot = pd.DataFrame(h2_tot, index=list(h2_tot.keys()), columns=['Cluster #0'])
        return pd.DataFrame(h2_df_ts), pd.DataFrame(h2_df_tot)

    def run(self):
        # TODO: add control type as input!
        clusters = self.create_clusters()  # initialize clusters
        power_to_clusters = self.even_split_power()
        h2_df_ts = pd.DataFrame()
        h2_df_tot = pd.DataFrame()

        col_names = []
        start = time.perf_counter()
        for ci in range(len(clusters)):
            cl_name = f"Cluster #{ci}"
            col_names.append(cl_name)
            h2_ts, h2_tot = clusters[ci].run(power_to_clusters[ci])
            # h2_dict_ts['Cluster #{}'.format(ci)] = h2_ts

            h2_ts_temp = pd.Series(h2_ts, name=cl_name)
            h2_tot_temp = pd.Series(h2_tot, name=cl_name)
            if len(h2_df_tot) == 0:
                # h2_df_ts=pd.concat([h2_df_ts,h2_ts_temp],axis=0,ignore_index=False)
                h2_df_tot = pd.concat([h2_df_tot, h2_tot_temp], axis=0, ignore_index=False)
                h2_df_tot.columns = col_names

                h2_df_ts = pd.concat([h2_df_ts, h2_ts_temp], axis=0, ignore_index=False)
                h2_df_ts.columns = col_names
            else:
                # h2_df_ts = h2_df_ts.join(h2_ts_temp)
                h2_df_tot = h2_df_tot.join(h2_tot_temp)
                h2_df_tot.columns = col_names

                h2_df_ts = h2_df_ts.join(h2_ts_temp)
                h2_df_ts.columns = col_names

        end = time.perf_counter()
        self.clusters = clusters
        if self.verbose:
            print(f"Took {round(end - start, 3)} sec to run the RUN function")
        return h2_df_ts, h2_df_tot
        # return h2_dict_ts, h2_df_tot

    def even_split_power(self):
        start = time.perf_counter()
        # determine how much power to give each cluster
        num_clusters_on = np.floor(self.input_power_kw / self.cluster_min_power)
        num_clusters_on = np.where(
            num_clusters_on > self.num_clusters, self.num_clusters, num_clusters_on
        )
        power_per_cluster = [
            self.input_power_kw[ti] / num_clusters_on[ti] if num_clusters_on[ti] > 0 else 0
            for ti, pwr in enumerate(self.input_power_kw)
        ]

        power_per_to_active_clusters = np.array(power_per_cluster)
        power_to_clusters = np.zeros((len(self.input_power_kw), self.num_clusters))
        for i, cluster_power in enumerate(
            power_per_to_active_clusters
        ):  # np.arange(0,self.n_stacks,1):
            clusters_off = self.num_clusters - int(num_clusters_on[i])
            no_power = np.zeros(clusters_off)
            with_power = cluster_power * np.ones(int(num_clusters_on[i]))
            tot_power = np.concatenate((with_power, no_power))
            power_to_clusters[i] = tot_power

        # power_to_clusters = np.repeat([power_per_cluster],self.num_clusters,axis=0)
        end = time.perf_counter()

        if self.verbose:
            print(f"Took {round(end - start, 3)} sec to run even_split_power function")
        # rows are power, columns are stacks [300 x n_stacks]

        return np.transpose(power_to_clusters)

    def max_h2_cntrl(self):
        # run as many at lower power as possible
        ...

    def min_deg_cntrl(self):
        # run as few as possible
        ...

    def create_clusters(self):
        start = time.perf_counter()
        # TODO fix the power input - don't make it required!
        # in_dict={'dt':3600}
        clusters = PEMClusters(self.cluster_cap_mw, self.plant_life_yrs, **self.user_params)
        stacks = [clusters] * self.num_clusters
        end = time.perf_counter()
        if self.verbose:
            print(f"Took {round(end - start, 3)} sec to run the create clusters")
        return stacks
