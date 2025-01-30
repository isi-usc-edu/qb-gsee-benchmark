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
            self.standard_report_output_directory,
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

        # NOTE: some plots created during ML processing and already in the `ml_artifacts` directory.

        # add content to README.md
        self.create_readme_content()

        # convert README.md to index.html and to PDF
        # step 1: convert markdown to HTML
        self.convert_readme_markdown_to_html()
        # step 2: convert HTML to PDF
        self.convert_readme_html_to_pdf()








    def create_plot_histogram_of_number_of_orbitals(self) -> None:
        """TODO: docstring
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
            self.standard_report_output_directory,
            f"num_orbitals_histogram.png")
        )
        plt.close()













    def create_plot_num_orbitals_vs_utility_for_each_hamiltonian(self) -> None:
        """TODO: docstring
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
            self.standard_report_output_directory,
            f"num_orbitals_vs_utility.png")
        )
        plt.close()
    










    def create_plot_num_orbitals_vs_run_time_for_all_solvers(self) -> None:
        """TODO: docstring
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
                label=f"Success {solver_short_name} ({solver_uuid[:4]}...)"
            )
            df_failed = df[df["label"]==False] # filter by failed to solve
            plt.scatter(
                df_failed["num_orbitals"].values,
                df_failed["overall_run_time_seconds"].values,
                color=colors[series_counter],
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Failed {solver_short_name} ({solver_uuid[:4]}...)"
            )
            series_counter += 1
        # plot in linear run time y-scale:
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.standard_report_output_directory,
            f"solver_num_orbs_vs_runtime_scatter_plot.png")
        )

        # plot in log(run time) y-scale:
        plt.yscale("log")
        plt.ylabel("Overall run time in seconds (log)")
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.standard_report_output_directory,
            f"solver_num_orbs_vs_log_runtime_scatter_plot.png")
        )

        plt.close()
        





    def create_plot_log_fci_dim_vs_run_time_for_all_solvers(self) -> None:
        """TODO: docstring
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
                label=f"Success {solver_short_name} ({solver_uuid[:4]}...)"
            )
            df_failed = df[df["label"]==False] # filter by failed to solve
            plt.scatter(
                df_failed["log_fci_dim"].values,
                df_failed["overall_run_time_seconds"].values,
                color=colors[series_counter],
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Failed {solver_short_name} ({solver_uuid[:4]}...)"
            )
            series_counter += 1
        # plot in linear run time y-scale:
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.standard_report_output_directory,
            f"log_fci_dim_vs_runtime_all_solvers_plot.png")
        )

        # plot in log(run time) y-scale:
        plt.yscale("log")
        plt.ylabel("Overall run time in seconds (log)")
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.standard_report_output_directory,
            f"log_fci_dim_vs_log_runtime_all_solvers_plot.png")
        )

        plt.close()
        








    def create_plot_quantum_vs_classical_num_orbitals_vs_run_time(self) -> None:
        """TODO: docstring
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
            self.standard_report_output_directory,
            f"quantum_vs_classical_solver_num_orbs_vs_runtime_scatter_plot.png")
        )

        # plot in log(run time) y-scale:
        plt.yscale("log")
        plt.ylabel("Overall run time in seconds (log)")
        # plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
        plt.tight_layout()
        plt.savefig(os.path.join(
            self.standard_report_output_directory,
            f"quantum_vs_classical_solver_num_orbs_vs_log_runtime_scatter_plot.png")
        )

        plt.close()
        







        






    def create_plot_num_orbitals_vs_run_time_for_each_solver(self) -> None:
        """TODO: docstring"""
        for solver_uuid in self.benchmark_data.solvers_dict:
            df = self.benchmark_data.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] # filter to solver_uuid
            solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
                        
            plt.figure()
            plt.title(f"Run time for {solver_short_name}/{solver_uuid[:4]}...")
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
                label=f"Task success {solver_short_name} ({solver_uuid[:4]}...)"
            )
            
            df_failed = df[df["label"]==False] # failed to solve the task
            plt.scatter(
                df_failed["num_orbitals"].values,
                df_failed["overall_run_time_seconds"].values,
                color="red", # red for failure
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Task failed {solver_short_name} ({solver_uuid[:4]}...)"
            )
            
            plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
            plt.tight_layout()
            plt.savefig(os.path.join(
                self.standard_report_output_directory,
                f"solver_{solver_uuid}_plot.png")
            )

            plt.close()
        



    def create_plot_log_fci_dim_vs_run_time_for_each_solver(self) -> None:
        """TODO: docstring"""
        for solver_uuid in self.benchmark_data.solvers_dict:
            df = self.benchmark_data.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] # filter to solver_uuid
            df = df[df["attempted"]==True] # filter to only attempted
            
            solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
                        
            plt.figure()
            plt.title(f"Run time for {solver_short_name}/{solver_uuid[:4]}...")
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
                label=f"Task success {solver_short_name} ({solver_uuid[:4]}...)"
            )
            
            df_failed = df[df["label"]==False] # failed to solve the task
            plt.scatter(
                df_failed["log_fci_dim"].values,
                df_failed["overall_run_time_seconds"].values,
                color="red", # red for failure
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Task failed {solver_short_name} ({solver_uuid[:4]}...)"
            )
            
            plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
            plt.tight_layout()
            plt.savefig(os.path.join(
                self.standard_report_output_directory,
                f"log_fci_dim_vs_runtime_solver_{solver_uuid}_plot.png")
            )

            plt.close()
        








    def create_plot_utility_capture_for_each_solver(self) -> None:
        """TODO: docstring"""
        
        for solver_uuid in self.benchmark_data.solvers_dict:
            df = self.benchmark_data.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] 
            total_utility = sum(df['Utility NPV $'].values)

            captured_utility = sum(df[df["label"]==True]["Utility NPV $"])
            captured_percent = 100*captured_utility/total_utility

            solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]
            plt.figure()
            plt.title(f"""
                Utility capture from {solver_short_name}/{solver_uuid[:4]}... \n
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
                label=f"Task success {solver_short_name} ({solver_uuid[:4]}...)"
            )
            
            df_failed = df[df["label"]==False] # failed to solve the task
            plt.scatter(
                df_failed["num_orbitals"].values,
                df_failed["Utility NPV $"].values,
                color="red", # red for failure
                marker="v", # triangle down for failure.
                edgecolor="black",
                label=f"Task failed {solver_short_name} ({solver_uuid[:4]}...)"
            )

            
            plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1)
            plt.tight_layout()
            plt.savefig(os.path.join(
                self.standard_report_output_directory,
                f"solver_{solver_uuid}_utility_capture_plot.png")
            )

            plt.close()











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
            file.write(f"![Number of orbitals histogram](num_orbitals_histogram.png)\n\n")
            file.write(f"![Utility estimate per Hamiltonian](num_orbitals_vs_utility.png)\n\n")
            
            


            file.write(f"# Solver Summary Statistics\n\n")
            file.write(f"number of unique participating solvers: {df['solver_uuid'].nunique()}\n\n")

            for solver_uuid in self.benchmark_data.ml_models_dict:
                solver_short_name = self.benchmark_data.solvers_dict[solver_uuid]["solver_short_name"]

                ml_model = self.benchmark_data.ml_models_dict[solver_uuid]
                if isinstance(ml_model, str):
                    # probably an error that we couldn't calculate the model.
                    verbiage = f"Solver: {solver_short_name}/{solver_uuid}, {ml_model}"
                else:
                    verbiage = f"Solver: {solver_short_name}/{solver_uuid}, ML Solvability Ratio: {ml_model.ml_solvability_ratio}, F1 Score: {ml_model.f1_score}"
                file.write(f"{verbiage}\n\n")
            
            file.write(f"![Solver scatter plot](solver_num_orbs_vs_runtime_scatter_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            file.write(f"![Solver scatter plot](solver_num_orbs_vs_log_runtime_scatter_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            file.write(f"![Quantum vs Classical scatter plot](quantum_vs_classical_solver_num_orbs_vs_log_runtime_scatter_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            file.write(f"![Solver logFCI scatter plot](log_fci_dim_vs_runtime_all_solvers_plot.png)\n\n")
            file.write(f"NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.\n\n")
            
            file.write(f"![Solver logFCI scatter plot, log(runtime)](log_fci_dim_vs_log_runtime_all_solvers_plot.png)\n\n")
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
                    if not isinstance(v, dict):
                        file.write(f"{k}: {v}\n\n")
                    else:
                        for kk, vv in v.items():
                            # only breaking out one more level of a dictionary
                            file.write(f"{kk}: {vv}\n\n")
                
                # writing out plots:
                file.write(f"![Solver success/failure plot](solver_{solver_uuid}_plot.png)\n\n")
                file.write(f"Note: plot only contains `attempted` tasks.\n\n")
                file.write(f"![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_{solver_uuid}_plot.png)\n\n")
                file.write(f"Note: plot only contains `attempted` tasks.\n\n")
                file.write(f"![Solver utility capture](solver_{solver_uuid}_utility_capture_plot.png)\n\n")
                file.write(f"![Solver miniML plot](plot_solver_{solver_uuid}.png)\n\n")
                file.write(f"Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.\n\n")
                file.write(f"![SHAP summary plot](shap_summary_plot_solver_{solver_uuid}.png)\n\n")
        
            # at the end of the file, write out NNMF information for ML models:
            # file.write(f"# Non-negative matrix factorization (ML latent space)\n\n")
            # file.write(f"![NNMF plot](nnmf_components.png)\n\n")
            # solver_uuid = list(self.benchmark_data.solvers_dict.keys())[0]# just get the first solver_uuid.
            # file.write(f"Features: {self.benchmark_data.ml_models_dict[solver_uuid].features}\n\n")
            # for i in range(2):
            #     file.write(f"Component {i+1}: {self.benchmark_data.ml_models_dict[solver_uuid].H[i]}\n\n")
    








    def convert_readme_markdown_to_html(self) -> None:
        """TODO: docstring"""
        readme_file = os.path.join(self.standard_report_output_directory, "README.md") 
        with open(readme_file, "r") as md_file:
            md_content = md_file.read()
        readme_html_file = os.path.join(self.standard_report_output_directory, "index.html")
        with open(readme_html_file, "w") as html_file:
            html_file.write(markdown.markdown(md_content))
        










    def convert_readme_html_to_pdf(self) -> None:
        """TODO: docstring ... depends on HTML"""
        readme_html_file = os.path.join(self.standard_report_output_directory, "index.html")
        readme_pdf_file = os.path.join(
            self.standard_report_output_directory,
            f"GSEE_benchmark_standard_report.pdf"
        )
        weasyprint.HTML(readme_html_file).write_pdf(readme_pdf_file)
        









        





        



