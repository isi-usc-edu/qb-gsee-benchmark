# Copyright 2025 L3Harris Technologies, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from qb_gsee_benchmark.benchmark_data import BenchmarkData
from qb_gsee_benchmark.utils import clear_or_create_output_directory
from qb_gsee_benchmark.utils import get_latest_ctime_within_dir

import logging
import os
import time
import shutil

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import cnames as color_names

import markdown
import weasyprint








class StandardReport:
    def __init__(
            self,
            benchmark_data: BenchmarkData,
            standard_report_output_directory: str
        ) -> None:
        """_summary_

        Depends:
            `BenchmarkData.performance_metrics_list` (`list`): A list of performance metrics (dictionary objects), most likely produced by `.calculate_performance_metrics()`.

        Args:
            benchmark_data (BenchmarkData): All of the data as a BenchmarkData object.
            standard_report_output_directory (str): The/relative/path/to/the/output/directory
        """

        np.random.seed(42)

        # check to make sure `performance_metrics` have been calculated.  (not calculated on init of BenchmarkData.)
        assert benchmark_data.performance_metrics_list is not None, \
            "You probably need to run BenchmarkData.calculate_performance_metrics() first!"
        
        # store input BenchmarkData object as an attribute
        self.benchmark_data = benchmark_data

        # clear/create output directory
        self.standard_report_output_directory = standard_report_output_directory
        clear_or_create_output_directory(output_directory=self.standard_report_output_directory)

        self.artifact_directory = "supporting_artifacts"
        self.full_artifact_directory_path = os.path.join(
            self.standard_report_output_directory,
            self.artifact_directory
        )
        clear_or_create_output_directory(output_directory=self.full_artifact_directory_path)

        # write out flattened data to output_directory
        o_path = os.path.join(
            self.standard_report_output_directory,
            f"data.csv"
        )
        self.benchmark_data.to_csv(o_path)


        # copy latest miniML plots/charts to the output_directory
        # these plots were created/updated when 
        # BenchmarkData.calculate_performance_metrics() was last called.
        shutil.copytree(
            "ml_artifacts",
            self.full_artifact_directory_path,
            dirs_exist_ok=True
        )

        # generate plots:
        self.create_plot_histogram_of_number_of_orbitals()
        self.create_plot_num_orbitals_vs_utility_for_each_hamiltonian()
        self.create_plot_num_orbitals_vs_run_time_for_all_solvers()
        self.create_plot_num_orbitals_vs_run_time_for_each_solver()
        self.create_plot_utility_capture_for_each_solver()
        self.create_plot_quantum_vs_classical_num_orbitals_vs_run_time()
        self.create_plot_log_fci_dim_vs_run_time_for_all_solvers()
        self.create_plot_log_fci_dim_vs_run_time_for_each_solver()
        self.create_plot_ml_v2_calibration_curves()

        # NOTE: some plots created during ML processing and already in the `ml_artifacts` directory.

        # add content to README.md
        self.create_readme_content()

        # convert README.md to index.html and to PDF
        # step 1: convert markdown to HTML
        self.convert_readme_markdown_to_html()
        # step 2: convert HTML to PDF
        self.convert_readme_html_to_pdf()








    def create_plot_histogram_of_number_of_orbitals(self) -> None:
        """Creates a histogram plot of all the Hamiltonians by number of orbitals.
        """

        df = self.benchmark_data.hamiltonian_features
        plt.figure()
        plt.hist(
            df["n_orbs"], # TODO: transition n_orbs to num_orbitals
            bins=[10*x for x in range(int(max(df["n_orbs"])/10+2))], # bin edges by 10
            edgecolor="black",
            alpha=0.7
        )
        plt.xlabel("Number of spatial orbitals")
        plt.ylabel("Number of Hamiltonians")
        plt.title("Histogram of Number of Spatial Orbitals")
        plt.savefig(os.path.join(
            self.full_artifact_directory_path,
            f"num_orbitals_histogram.png")
        )
        plt.close()













    def create_plot_num_orbitals_vs_utility_for_each_hamiltonian(self) -> None:
        """Create a scatter plot where each point is Hamiltonian and the position
        is (num_orbitals, utility)
        """

        # note that utility estimate data is repeated for each solver_uuid in `data`
        # just pick the first solver_uuid and filter by that.  
        # that filter provides a list of all Hamiltonians with no double counting.
        df = self.benchmark_data.all_data_df
        first_solver_uuid = self.benchmark_data.solvers_df["solver_uuid"].values[0]
        df = df[df["solver_uuid"]==first_solver_uuid]
        total_utility = sum(df['Utility NPV $'].values)
        plt.figure()
        plt.scatter(
            df["num_orbitals"].values,
            df["Utility NPV $"].values, 
        )
        plt.title(f"Utility estimate per Hamiltonian (total: ${total_utility:.1e})")
        plt.xlabel("Number of spatial orbitals")
        plt.xlim(0,10*np.ceil(max(df["num_orbitals"])/10))
        plt.ylabel("Utility estimate in USD")
        plt.savefig(os.path.join(
            self.full_artifact_directory_path,
            f"num_orbitals_vs_utility.png")
        )
        plt.close()
    










    def create_plot_num_orbitals_vs_run_time_for_all_solvers(self) -> None:
        """Create a scatter plot of all solvers where each point
        is one solver's attempt at a Hamiltonian.  Solvers are plotted
        with different colors.  
        """
        df = self.benchmark_data.all_data_df
        plt.figure()
        plt.title("Run time of solvers")
        plt.xlabel("Number of spatial orbitals")
        plt.xlim(0,10*np.ceil(max(df["num_orbitals"])/10))
        plt.ylabel("Overall run time in seconds")
        
        # colors = [tuple(np.random.rand(3)) for _ in range(len(solver_uuid_dict))]
        p_list = np.random.permutation(len(self.benchmark_data.solvers_dict))
        colors = [ list(color_names.keys())[i] for i in p_list ]
        # use "normal" colors first except for blue, red, and black
        # ... then dig deep into the color list.
        colors = ['c', 'm', 'y', 'g', 'w'] + colors
        
        # markers = ['o', 's', '^', 'D', 'p', '*', 'H', 'X', 'v', '<']
        series_counter = 0
        for solver_uuid in self.benchmark_data.solvers_dict:
            solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
            df = self.benchmark_data.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] # filter by solver...
            df = df[df["attempted"]==True] # filter by attempted
            df_solved = df[df["label"]==True] # filter by solved!
            plt.scatter(
                df_solved["num_orbitals"].values,
                df_solved["overall_run_time_seconds"].values,
                color=colors[series_counter],
                edgecolor="black",
                marker="^", # triangle up for success.
                label=f"Success {solver_short_name} ({solver_uuid[:6]}...)"
            )
            df_failed = df[df["label"]==False] # filter by failed to solve
            plt.scatter(
                df_failed["num_orbitals"].values,
                df_failed["overall_run_time_seconds"].values,
                color=colors[series_counter],
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Failed {solver_short_name} ({solver_uuid[:6]}...)"
            )
            series_counter += 1
        # plot in linear run time y-scale:
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.full_artifact_directory_path,
            f"solver_num_orbs_vs_runtime_scatter_plot.png")
        )

        # plot in log(run time) y-scale:
        plt.yscale("log")
        plt.ylabel("Overall run time in seconds (log)")
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.full_artifact_directory_path,
            f"solver_num_orbs_vs_log_runtime_scatter_plot.png")
        )

        plt.close()
        





    def create_plot_log_fci_dim_vs_run_time_for_all_solvers(self) -> None:
        """Create a scatter plot of all solvers where each point
        is one solver's attempt at a Hamiltonian.  Solvers are plotted
        with different colors.  
        """
        df = self.benchmark_data.all_data_df
        plt.figure()
        plt.title("Run time of solvers")
        plt.xlabel("Log(FCI size)")
        plt.xlim([0,self.benchmark_data.all_data_df["log_fci_dim"].max()])
        plt.ylabel("Overall run time in seconds")
        
        # colors = [tuple(np.random.rand(3)) for _ in range(len(solver_uuid_dict))]
        p_list = np.random.permutation(len(self.benchmark_data.solvers_dict))
        colors = [ list(color_names.keys())[i] for i in p_list ]
        # use "normal" colors first except for blue, red, and black
        # ... then dig deep into the color list.
        colors = ['c', 'm', 'y', 'g', 'w'] + colors
        
        # markers = ['o', 's', '^', 'D', 'p', '*', 'H', 'X', 'v', '<']
        series_counter = 0
        for solver_uuid in self.benchmark_data.solvers_dict:
            solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
            df = self.benchmark_data.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] # filter by solver...
            df = df[df["attempted"]==True] # filter by attempted
            df_solved = df[df["label"]==True] # filter by solved!
            plt.scatter(
                df_solved["log_fci_dim"].values,
                df_solved["overall_run_time_seconds"].values,
                color=colors[series_counter],
                edgecolor="black",
                marker="^", # triangle up for success.
                label=f"Success {solver_short_name} ({solver_uuid[:6]}...)"
            )
            df_failed = df[df["label"]==False] # filter by failed to solve
            plt.scatter(
                df_failed["log_fci_dim"].values,
                df_failed["overall_run_time_seconds"].values,
                color=colors[series_counter],
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Failed {solver_short_name} ({solver_uuid[:6]}...)"
            )
            series_counter += 1
        # plot in linear run time y-scale:
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.full_artifact_directory_path,
            f"log_fci_dim_vs_runtime_all_solvers_plot.png")
        )

        # plot in log(run time) y-scale:
        plt.yscale("log")
        plt.ylabel("Overall run time in seconds (log)")
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.full_artifact_directory_path,
            f"log_fci_dim_vs_log_runtime_all_solvers_plot.png")
        )

        plt.close()
        








    def create_plot_quantum_vs_classical_num_orbitals_vs_run_time(self) -> None:
        """ Create a scatter plot of all solvers where each point
        is one solver's attempt at a Hamiltonian.  Quantum solvers are blue
        and classical solvers are red.  
        """
        df = self.benchmark_data.all_data_df
        plt.figure()
        plt.title("Run time of Classical (red) vs Quantum (blue) solvers")
        plt.xlabel("Number of spatial orbitals")
        plt.xlim(0,10*np.ceil(max(df["num_orbitals"])/10))
        plt.ylabel("Overall run time in seconds")
        
        df = df[df["attempted"]==True] # filter by attempted
        df_quantum = df[df["is_resource_estimate"]==True] # filter by quantum
        df_classical = df[df["is_resource_estimate"]==False] # filter by classical
        
        df_quantum_solved = df_quantum[df_quantum["label"]==True] # filter by solved!
        plt.scatter(
            df_quantum_solved["num_orbitals"].values,
            df_quantum_solved["overall_run_time_seconds"].values,
            color="blue",
            edgecolor="black",
            marker="^", # triangle up for success.
            label=f"Success quantum solver"
        )
        df_quantum_failed = df_quantum[df_quantum["label"]==False] # filter by failed!
        plt.scatter(
            df_quantum_failed["num_orbitals"].values,
            df_quantum_failed["overall_run_time_seconds"].values,
            color="blue",
            edgecolor="black",
            marker="v", # triangle down for failure
            label=f"Failed quantum solver"
        )
        df_classical_solved = df_classical[df_classical["label"]==True] # filter by solved!
        plt.scatter(
            df_classical_solved["num_orbitals"].values,
            df_classical_solved["overall_run_time_seconds"].values,
            color="red",
            edgecolor="black",
            marker="^", # triangle up for success.
            label=f"Success classical solver"
        )
        df_classical_failed = df_classical[df_classical["label"]==False] # filter by failed!
        plt.scatter(
            df_classical_failed["num_orbitals"].values,
            df_classical_failed["overall_run_time_seconds"].values,
            color="red",
            edgecolor="black",
            marker="v", # triangle down for failure
            label=f"Failed classical solver"
        )


        # plot in linear run time y-scale:
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.full_artifact_directory_path,
            f"quantum_vs_classical_solver_num_orbs_vs_runtime_scatter_plot.png")
        )

        # plot in log(run time) y-scale:
        plt.yscale("log")
        plt.ylabel("Overall run time in seconds (log)")
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.full_artifact_directory_path,
            f"quantum_vs_classical_solver_num_orbs_vs_log_runtime_scatter_plot.png")
        )

        plt.close()
        







        






    def create_plot_num_orbitals_vs_run_time_for_each_solver(self) -> None:
        """Create ONE scatter plot FOR ONE solver where each point
        is one solver's attempt at a Hamiltonian.  This creates num_solvers plots.
        """
        for solver_uuid in self.benchmark_data.solvers_dict:
            df = self.benchmark_data.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] # filter to solver_uuid
            solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
                        
            plt.figure()
            plt.title(f"Run time for {solver_short_name}/{solver_uuid[:6]}...")
            plt.xlabel("Number of spatial orbitals")
            plt.xlim(0,10*np.ceil(max(df["num_orbitals"])/10))
            plt.ylabel("Overall run time in seconds")
            
            df = df[df["attempted"]==True] # filter to only attempted
            
            df_solved = df[df["label"]==True] # Solved!
            plt.scatter(
                df_solved["num_orbitals"].values,
                df_solved["overall_run_time_seconds"].values,
                color="blue", # blue for success
                marker="^", # triangle up for success.
                edgecolor="black",
                label=f"Task success {solver_short_name} ({solver_uuid[:6]}...)"
            )
            
            df_failed = df[df["label"]==False] # failed to solve the task
            plt.scatter(
                df_failed["num_orbitals"].values,
                df_failed["overall_run_time_seconds"].values,
                color="red", # red for failure
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Task failed {solver_short_name} ({solver_uuid[:6]}...)"
            )
            
            plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
            plt.tight_layout()
            plt.savefig(os.path.join(
                self.full_artifact_directory_path,
                f"solver_{solver_uuid}_plot.png")
            )

            plt.close()
        



    def create_plot_log_fci_dim_vs_run_time_for_each_solver(self) -> None:
        """Create ONE scatter plot FOR ONE solver where each point
        is one solver's attempt at a Hamiltonian.  This creates num_solvers plots.
        """
        for solver_uuid in self.benchmark_data.solvers_dict:
            df = self.benchmark_data.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] # filter to solver_uuid
            df = df[df["attempted"]==True] # filter to only attempted
            
            solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
                        
            plt.figure()
            plt.title(f"Run time for {solver_short_name}/{solver_uuid[:6]}...")
            plt.xlabel("log(FCI size)")
            plt.xlim([0,self.benchmark_data.all_data_df["log_fci_dim"].max()])
            plt.ylabel("Overall run time in seconds")
            
            
            df_solved = df[df["label"]==True] # Solved!
            plt.scatter(
                df_solved["log_fci_dim"].values,
                df_solved["overall_run_time_seconds"].values,
                color="blue", # blue for success
                marker="^", # triangle up for success.
                edgecolor="black",
                label=f"Task success {solver_short_name} ({solver_uuid[:6]}...)"
            )
            
            df_failed = df[df["label"]==False] # failed to solve the task
            plt.scatter(
                df_failed["log_fci_dim"].values,
                df_failed["overall_run_time_seconds"].values,
                color="red", # red for failure
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Task failed {solver_short_name} ({solver_uuid[:6]}...)"
            )
            
            plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
            plt.tight_layout()
            plt.savefig(os.path.join(
                self.full_artifact_directory_path,
                f"log_fci_dim_vs_runtime_solver_{solver_uuid}_plot.png")
            )

            plt.close()
        








    def create_plot_utility_capture_for_each_solver(self) -> None:
        """Create ONE scatter plot FOR ONE solver where each point
        is one solver's attempt at a Hamiltonian.  This creates num_solvers plots.
        """
        
        for solver_uuid in self.benchmark_data.solvers_dict:
            df = self.benchmark_data.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] 
            total_utility = sum(df['Utility NPV $'].values)

            captured_utility = sum(df[df["label"]==True]["Utility NPV $"])
            captured_percent = 100*captured_utility/total_utility

            solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
            plt.figure()
            plt.title(f"""
                Utility capture from {solver_short_name}/{solver_uuid[:6]}... \n
                (captured: ${captured_utility:.1e}/{total_utility:.1e}, approximately {captured_percent:.1e}%)            
                """)
            plt.xlabel("Number of spatial orbitals")
            plt.xlim(0,10*np.ceil(max(df["num_orbitals"])/10))
            plt.ylabel("Utility estimate in USD")
            
            df_solved = df[df["label"]==True] # Solved!
            plt.scatter(
                df_solved["num_orbitals"].values,
                df_solved["Utility NPV $"].values,
                color="blue", # blue for success
                marker="^", # triangle up for success.
                edgecolor="black",
                label=f"Task success {solver_short_name} ({solver_uuid[:6]}...)"
            )
            
            df_failed = df[df["label"]==False] # failed to solve the task
            plt.scatter(
                df_failed["num_orbitals"].values,
                df_failed["Utility NPV $"].values,
                color="red", # red for failure
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Task failed {solver_short_name} ({solver_uuid[:6]}...)"
            )

            
            plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
            plt.tight_layout()
            plt.savefig(os.path.join(
                self.full_artifact_directory_path,
                f"solver_{solver_uuid}_utility_capture_plot.png")
            )

            plt.close()











    @staticmethod
    def _ml_v2_calibration_plot_filename(solver_uuid: str) -> str:
        return f"ml_v2_calibration_solver_{solver_uuid}.png"


    @staticmethod
    def _calibration_rows_for_primary_features(ml_v2: dict) -> list[dict]:
        rows = ml_v2.get("calibration") or []
        if not rows:
            return []
        preferred = [row for row in rows if row.get("feature_set") == "full16_plus_b2"]
        if preferred:
            return preferred
        fallback = [row for row in rows if row.get("feature_set") == "full16"]
        return fallback if fallback else rows


    def create_plot_ml_v2_calibration_curves(self) -> None:
        """Create per-solver reliability curves from ML-v2 calibration bins."""
        for performance_metrics in self.benchmark_data.performance_metrics_list:
            solver_uuid = performance_metrics.get("solver_uuid")
            if not solver_uuid:
                continue
            ml_metrics = performance_metrics.get("ml_metrics", {})
            ml_v2 = ml_metrics.get("ml_v2", {}) if isinstance(ml_metrics, dict) else {}
            rows = self._calibration_rows_for_primary_features(ml_v2)
            plot_rows = []
            for row in rows:
                try:
                    mean_probability = float(row.get("mean_probability"))
                    observed_rate = float(row.get("observed_positive_rate"))
                except (TypeError, ValueError):
                    continue
                if np.isnan(mean_probability) or np.isnan(observed_rate):
                    continue
                plot_rows.append(
                    {
                        "mean_probability": mean_probability,
                        "observed_positive_rate": observed_rate,
                        "n": row.get("n", 1) or 1,
                        "feature_set": row.get("feature_set", ""),
                    }
                )
            if not plot_rows:
                continue
            solver_short_name = performance_metrics.get("solver_short_name", solver_uuid[:8])
            plt.figure(figsize=(4.8, 4.2))
            plt.plot([0, 1], [0, 1], color="black", linewidth=1.0, linestyle="--", label="Perfect calibration")
            x = [row["mean_probability"] for row in plot_rows]
            y = [row["observed_positive_rate"] for row in plot_rows]
            sizes = [max(20.0, 8.0 * float(row["n"])) for row in plot_rows]
            feature_set = plot_rows[0].get("feature_set", "")
            plt.scatter(x, y, s=sizes, color="tab:blue", alpha=0.75, edgecolor="black", label=feature_set)
            plt.xlabel("Mean predicted probability")
            plt.ylabel("Observed positive rate")
            plt.xlim(0, 1)
            plt.ylim(0, 1)
            plt.title(f"ML v2 calibration: {solver_short_name}")
            plt.legend(loc="best")
            plt.tight_layout()
            plt.savefig(os.path.join(
                self.full_artifact_directory_path,
                self._ml_v2_calibration_plot_filename(solver_uuid),
            ))
            plt.close()


    @staticmethod
    def _format_metric(value) -> str:
        if value is None:
            return "n/a"
        try:
            if np.isnan(value):
                return "n/a"
        except TypeError:
            pass
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)


    def _write_ml_summary_line(self, file, solver_short_name: str, solver_uuid: str, ml_metrics: dict) -> None:
        ml_v2 = ml_metrics.get("ml_v2", {}) if isinstance(ml_metrics, dict) else {}
        primary = ml_v2.get("primary_result") or {}
        comparison = ml_v2.get("family_grouped_feature_comparison") or {}
        leakage_rows = ml_v2.get("random_vs_grouped_leakage") or []
        leakage = None
        for row in leakage_rows:
            if row.get("feature_set") in {"full16_plus_b2", "full16"}:
                leakage = row.get("average_precision_random_minus_grouped")
                break

        if primary:
            file.write(
                f"Solver: {solver_short_name}/{solver_uuid}, "
                f"ML v2 family-grouped AP: {self._format_metric(primary.get('average_precision'))}, "
                f"Brier: {self._format_metric(primary.get('brier'))}, "
                f"empirical coverage: {self._format_metric(primary.get('empirical_instance_coverage'))}"
            )
            delta = comparison.get("full16_plus_b2_minus_size_only_average_precision")
            if delta is not None:
                file.write(f", AP(full16+B2 - size-only): {self._format_metric(delta)}")
            if leakage is not None:
                file.write(f", random-minus-grouped AP: {self._format_metric(leakage)}")
            file.write("\n\n")
        else:
            reason = ml_v2.get("reason", "ML v2 not calculated")
            file.write(f"Solver: {solver_short_name}/{solver_uuid}, ML v2: {reason}\n\n")

        legacy_ratio = ml_metrics.get("legacy_solvability_ratio", ml_metrics.get("solvability_ratio"))
        legacy_f1 = ml_metrics.get("f1_score")
        file.write(
            "Legacy MiniML grid solvability ratio (not OOF): "
            f"{self._format_metric(legacy_ratio)}; legacy in-sample F1: {legacy_f1}\n\n"
        )


    @staticmethod
    def _beats_size_only_label(delta) -> str:
        if delta is None:
            return "n/a"
        try:
            if np.isnan(delta):
                return "n/a"
        except TypeError:
            pass
        return "Yes" if float(delta) > 0.0 else "No"


    def _ml_v2_leaderboard_rows(self, performance_metrics_by_solver: dict) -> list[dict]:
        rows = []
        for solver_uuid in self.benchmark_data.solvers_dict:
            solver = self.benchmark_data.solvers_dict[solver_uuid]
            performance_metrics = performance_metrics_by_solver.get(solver_uuid, {})
            top_level = performance_metrics.get("top_level_results", {})
            ml_metrics = performance_metrics.get("ml_metrics", {}) if isinstance(performance_metrics, dict) else {}
            ml_v2 = ml_metrics.get("ml_v2", {}) if isinstance(ml_metrics, dict) else {}
            primary = ml_v2.get("primary_result") or {}
            comparison = ml_v2.get("family_grouped_feature_comparison") or {}
            delta = comparison.get("full16_plus_b2_minus_size_only_average_precision")
            if delta is None:
                delta = comparison.get("full16_minus_size_only_average_precision")
            rows.append(
                {
                    "solver_short_name": solver.get("solver_short_name", ""),
                    "solver_uuid": solver_uuid,
                    "tasks_attempted": top_level.get("number_of_tasks_attempted"),
                    "tasks_solved": top_level.get("number_of_tasks_solved"),
                    "ml_v2_average_precision": primary.get("average_precision"),
                    "ml_v2_brier": primary.get("brier"),
                    "ml_v2_empirical_instance_coverage": primary.get("empirical_instance_coverage"),
                    "ap_delta_vs_size_only": delta,
                    "beats_size_only": self._beats_size_only_label(delta),
                    "legacy_grid_solvability_ratio": ml_metrics.get(
                        "legacy_solvability_ratio",
                        ml_metrics.get("solvability_ratio"),
                    ),
                }
            )

        def sort_key(row: dict):
            ap = row.get("ml_v2_average_precision")
            try:
                if ap is None or np.isnan(ap):
                    return (1, 0.0, row["solver_short_name"])
            except TypeError:
                return (1, 0.0, row["solver_short_name"])
            return (0, -float(ap), row["solver_short_name"])

        return sorted(rows, key=sort_key)


    def _write_ml_v2_leaderboard_table(self, file, performance_metrics_by_solver: dict) -> None:
        rows = self._ml_v2_leaderboard_rows(performance_metrics_by_solver)
        file.write("## ML v2 Out-of-Fold Leaderboard\n\n")
        file.write(
            "Primary ML-v2 metrics are family-grouped out-of-fold results for the "
            "regularized logistic model. The `Beats size-only?` column compares the "
            "primary feature set against the `{n_elec, n_orbs}` baseline by average "
            "precision; legacy MiniML solvability/F1 values are listed separately "
            "because they are not out-of-fold metrics.\n\n"
        )
        if not rows:
            file.write("No solver performance metrics available.\n\n")
            return
        headers = [
            "Solver",
            "Attempted",
            "Solved",
            "OOF AP",
            "Brier",
            "Empirical coverage",
            "AP delta vs size-only",
            "Beats size-only?",
            "Legacy grid solvability",
        ]
        file.write("| " + " | ".join(headers) + " |\n")
        file.write("|" + "|".join("---" for _ in headers) + "|\n")
        for row in rows:
            solver_label = f"{row['solver_short_name']} ({row['solver_uuid'][:8]})"
            values = [
                solver_label,
                self._format_metric(row.get("tasks_attempted")),
                self._format_metric(row.get("tasks_solved")),
                self._format_metric(row.get("ml_v2_average_precision")),
                self._format_metric(row.get("ml_v2_brier")),
                self._format_metric(row.get("ml_v2_empirical_instance_coverage")),
                self._format_metric(row.get("ap_delta_vs_size_only")),
                row.get("beats_size_only", "n/a"),
                self._format_metric(row.get("legacy_grid_solvability_ratio")),
            ]
            file.write("| " + " | ".join(str(value) for value in values) + " |\n")
        file.write("\n")


    def _write_ml_metrics_block(self, file, ml_metrics: dict) -> None:
        ml_v2 = ml_metrics.get("ml_v2", {}) if isinstance(ml_metrics, dict) else {}
        primary = ml_v2.get("primary_result") or {}
        comparison = ml_v2.get("family_grouped_feature_comparison") or {}
        outcomes = ml_v2.get("two_channel_outcome_counts") or {}

        file.write("ml_v2_primary_model: " + str(ml_v2.get("primary_model")) + "\n\n")
        file.write("ml_v2_primary_protocol: " + str(primary.get("protocol")) + "\n\n")
        file.write("ml_v2_primary_feature_set: " + str(primary.get("feature_set")) + "\n\n")
        file.write("ml_v2_average_precision: " + self._format_metric(primary.get("average_precision")) + "\n\n")
        file.write("ml_v2_brier: " + self._format_metric(primary.get("brier")) + "\n\n")
        file.write("ml_v2_empirical_instance_coverage: " + self._format_metric(primary.get("empirical_instance_coverage")) + "\n\n")
        file.write(
            "ml_v2_full16_plus_b2_minus_size_only_average_precision: "
            + self._format_metric(comparison.get("full16_plus_b2_minus_size_only_average_precision"))
            + "\n\n"
        )
        file.write("two_channel_outcome_counts: " + str(outcomes) + "\n\n")
        if outcomes:
            file.write("| outcome | count |\n")
            file.write("|---|---:|\n")
            for outcome, count in sorted(outcomes.items()):
                file.write(f"| {outcome} | {count} |\n")
            file.write("\n")
        file.write(
            "legacy_solvability_ratio: "
            + self._format_metric(ml_metrics.get("legacy_solvability_ratio", ml_metrics.get("solvability_ratio")))
            + "\n\n"
        )
        file.write("legacy_in_sample_f1_score: " + str(ml_metrics.get("f1_score")) + "\n\n")


    def create_readme_content(self) -> None:
        readme_file = os.path.join(self.standard_report_output_directory, "README.md")
        with open(readme_file, "w") as file:
            file.write(f"# GSEE Benchmark Standard Report\n\n")
            file.write(f"Report based on data from {self.benchmark_data.timestamp}\n\n")
            file.write(f"[https://github.com/isi-usc-edu/qb-gsee-benchmark](https://github.com/isi-usc-edu/qb-gsee-benchmark)\n\n")
            
            last_modified_time = time.ctime(os.path.getmtime(self.benchmark_data.hamiltonian_features_csv_file_name))
            file.write(f"Input data: `{self.benchmark_data.hamiltonian_features_csv_file_name}`, last modified {last_modified_time}\n\n")
            
            num_features_calculated = len(self.benchmark_data.hamiltonian_features)
            num_tasks = 0
            for problem_instance in self.benchmark_data.problem_instance_list:
                num_tasks += len(problem_instance["tasks"]) # count up tasks.
            if num_features_calculated < num_tasks:
                file.write(f"WARNING!  We only have features calculated for \
                            {num_features_calculated}/{num_tasks} Hamiltonians. \
                            This report is based on partial results!\n\n")

            last_modified_time = time.ctime(os.path.getmtime(self.benchmark_data.utility_estimation_csv_file_name))
            file.write(f"Input data: `{self.benchmark_data.utility_estimation_csv_file_name}`, last modified {last_modified_time}\n\n")

            c = get_latest_ctime_within_dir(self.benchmark_data.problem_instances_directory)
            file.write(f"Latest creation time for a `problem_instance.json` file: {time.ctime(c)}\n\n")
            
            c = get_latest_ctime_within_dir(self.benchmark_data.solution_files_directory)
            file.write(f"Latest creation time for a `solution.json` file: {time.ctime(c)}\n\n")

            df = self.benchmark_data.all_data_df
            file.write(f"# Problem Instance Summary Statistics\n\n")
            file.write(f"number of `problem_instances`: {len(self.benchmark_data.problem_instance_list)}.\n\n")

            max_num_tasks = 0
            for problem_instance in self.benchmark_data.problem_instance_list:
                if len(problem_instance["tasks"]) > max_num_tasks:
                    max_num_tasks = len(problem_instance["tasks"])
                    problem_instance_uuid = problem_instance["problem_instance_uuid"]
                    problem_instance_short_name = problem_instance["short_name"]

            file.write(f"`problem_instance.json` with the most tasks: {max_num_tasks} ({problem_instance_short_name}/{problem_instance_uuid})\n\n")
            file.write(f"number of Hamiltonians (i.e., tasks) we have features calculated for: {num_features_calculated}\n\n")
            file.write(f"minimum number of orbitals: {np.min(df['num_orbitals'])}\n\n")
            file.write(f"median number of orbitals: {np.median(df['num_orbitals'])}\n\n")
            file.write(f"maximum number of orbitals: {np.max(df['num_orbitals'])}\n\n")
            file.write(f"![Number of orbitals histogram]({self.artifact_directory}/num_orbitals_histogram.png)\n\n")
            file.write(f"![Utility estimate per Hamiltonian]({self.artifact_directory}/num_orbitals_vs_utility.png)\n\n")
            
            


            file.write(f"# Solver Summary Statistics\n\n")
            file.write(f"number of unique participating solvers: {df['solver_uuid'].nunique()}\n\n")

            performance_metrics_by_solver = {
                pm["solver_uuid"]: pm
                for pm in self.benchmark_data.performance_metrics_list
            }
            self._write_ml_v2_leaderboard_table(file, performance_metrics_by_solver)
            file.write("## Per-Solver ML Details\n\n")
            for solver_uuid in self.benchmark_data.solvers_dict:
                solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
                performance_metrics = performance_metrics_by_solver.get(solver_uuid, {})
                ml_metrics = performance_metrics.get("ml_metrics", {})
                self._write_ml_summary_line(file, solver_short_name, solver_uuid, ml_metrics)
            
            file.write(f"![Solver scatter plot]({self.artifact_directory}/solver_num_orbs_vs_runtime_scatter_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            file.write(f"![Solver scatter plot]({self.artifact_directory}/solver_num_orbs_vs_log_runtime_scatter_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            file.write(f"![Quantum vs Classical scatter plot]({self.artifact_directory}/quantum_vs_classical_solver_num_orbs_vs_log_runtime_scatter_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            file.write(f"![Solver logFCI scatter plot]({self.artifact_directory}/log_fci_dim_vs_runtime_all_solvers_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            file.write(f"![Solver logFCI scatter plot, log(runtime)]({self.artifact_directory}/log_fci_dim_vs_log_runtime_all_solvers_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            
            
            


           
            solvers = self.benchmark_data.solvers_dict
            for solver_uuid in solvers:
                solver = solvers[solver_uuid]

                found_it = False
                for performance_metrics in self.benchmark_data.performance_metrics_list:
                    if performance_metrics["solver_uuid"] == solver_uuid:
                        # we have located performance_metrics for solver_uuid
                        found_it = True
                        break
                    else:
                        continue
                assert found_it, f"Can't find associated performance_metrics for solver_uuid {solver_uuid}"

                performance_metrics_fields = [
                    "performance_metrics_uuid",
                    "creation_timestamp",
                    "top_level_results",
                    "ml_metrics"                
                ]
                
                file.write(f"## Solver {solver['solver_short_name']}, {solver['solver_uuid']}\n\n")
                
                # writing out solver_details:
                for k,v in solver.items():
                    file.write(f"{k}:{v}\n\n")
                
                # writing out some (not all) performance metrics.
                filtered_performance_metrics = {key: performance_metrics[key] for key in performance_metrics_fields if key in performance_metrics}
                for k, v in filtered_performance_metrics.items():
                    if k == "ml_metrics" and isinstance(v, dict):
                        self._write_ml_metrics_block(file, v)
                        ml_v2 = v.get("ml_v2", {}) if isinstance(v, dict) else {}
                        if self._calibration_rows_for_primary_features(ml_v2):
                            file.write(
                                f"![ML v2 calibration curve]({self.artifact_directory}/{self._ml_v2_calibration_plot_filename(solver_uuid)})\n\n"
                            )
                    elif not isinstance(v, dict):
                        file.write(f"{k}: {v}\n\n")
                    else:
                        for kk, vv in v.items():
                            file.write(f"{kk}: {vv}\n\n")
                
                # writing out plots:
                file.write(f"![Solver success/failure plot]({self.artifact_directory}/solver_{solver_uuid}_plot.png)\n\n")
                file.write(f"Note: plot only contains `attempted` tasks.\n\n")
                file.write(f"![Solver success/failure logFCI plot]({self.artifact_directory}/log_fci_dim_vs_runtime_solver_{solver_uuid}_plot.png)\n\n")
                file.write(f"Note: plot only contains `attempted` tasks.\n\n")
                file.write(f"![Solver utility capture]({self.artifact_directory}/solver_{solver_uuid}_utility_capture_plot.png)\n\n")
                file.write(f"![Solver PCA plot]({self.artifact_directory}/PCA_embedding_plot_solver_{solver_uuid}.png)\n\n")
                file.write(f"![Solver NNMF plot]({self.artifact_directory}/NNMF_embedding_plot_solver_{solver_uuid}.png)\n\n")
                file.write(f"Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.\n\n")
                file.write(f"![SHAP summary plot]({self.artifact_directory}/shap_summary_plot_solver_{solver_uuid}.png)\n\n")
            
            # at the end of the file, write out NNMF information for ML models:
            file.write(f"# ML Feature Analysis\n\n")

            # find one solver_uuid that has an ML model (all of the following results will be the same)
            for solver_uuid in self.benchmark_data.ml_models_dict:
                if isinstance(self.benchmark_data.ml_models_dict[solver_uuid], str):
                    continue # try the next one.
                else:
                    ml_model = self.benchmark_data.ml_models_dict[solver_uuid]
                    break # found a solver_uuid with an ML model.
                    
            file.write(f"![NNMF components plot]({self.artifact_directory}/nnmf_components.png)\n\n")
            file.write(f"Features: {ml_model.features}\n\n")
            for i in range(2):
                file.write(f"NNMF Component {i+1}: {ml_model.H[i]}\n\n")
            
            file.write(f"![PCA components plot]({self.artifact_directory}/pca_components.png)\n\n")
            file.write(f"Features: {ml_model.features}\n\n")
            for i in range(2):
                file.write(f"PCA Component {i+1}: {ml_model.pca.components_[i]}\n\n")

            file.write(f"![solver similarity: PCA space of area]({self.artifact_directory}/solver_similarity_in_PCA_space_of_area_summary.png)\n\n")
            file.write(f"![solver similarity: PCA space of SHAP]({self.artifact_directory}/solver_similarity_in_PCA_space_of_shap_summary.png)\n\n")
            file.write(f"![solver similarity: matrix/area]({self.artifact_directory}/solver_similarity_matrix_area_summary.png)\n\n")
            file.write(f"![solver similarity: matrix/SHAP values]({self.artifact_directory}/solver_similarity_matrix_shap_summary.png)\n\n")
            
                
            file.write(f"![Hamiltonian features correlation matrix]({self.artifact_directory}/hamiltonian_features_correlation_matrix_plot.png)\n\n")
            for feature in ml_model.features:
                file.write(f"![Histogram of Hamiltonian features: {feature}]({self.artifact_directory}/hamiltonian_feature_histogram_{feature}.png)\n\n")
            






    def convert_readme_markdown_to_html(self) -> None:
        """First, we need to convert the README.md file to HTML.  In a later
        method we will convert the HTML to PDF."""
        readme_file = os.path.join(self.standard_report_output_directory, "README.md") 
        with open(readme_file, "r") as md_file:
            md_content = md_file.read()
        readme_html_file = os.path.join(self.standard_report_output_directory, "index.html")
        with open(readme_html_file, "w") as html_file:
            html_file.write(markdown.markdown(md_content))
        










    def convert_readme_html_to_pdf(self) -> None:
        """We first converted the README.md to HTML in an earlier method. This
        method converts the HTML to a PDF.
        """

        readme_html_file = os.path.join(self.standard_report_output_directory, "index.html")
        readme_pdf_file = os.path.join(
            self.standard_report_output_directory,
            f"GSEE_benchmark_standard_report.pdf"
        )
        weasyprint.HTML(readme_html_file).write_pdf(readme_pdf_file)
        









        





        



