#!/bin/bash






# PRE_solution_files_20250124_0.000001_0.1us/
# PRE_solution_files_20250124_0.000001_1us/
# PRE_solution_files_20250124_0.0001_0.1us/
# PRE_solution_files_20250124_0.0001_1us/
# PRE_solution_files_20250124_0.0001_1us_parallel/


# PRE_config_0.000001_0.1us.json
# PRE_config_0.000001_1us.json
# PRE_config_0.0001_0.1us.json
# PRE_config_0.0001_1us.json
# PRE_config_0.0001_1us_parallel.json



./compute_all_PREs_script.py -i LRE_solution_files_before_PRE_20250124 -o PRE_solution_files_20250124_0.000001_0.1us --PRE_config_file PRE_config_0.000001_0.1us.json
./compute_all_PREs_script.py -i LRE_solution_files_before_PRE_20250124 -o PRE_solution_files_20250124_0.000001_1us --PRE_config_file PRE_config_0.000001_1us.json
./compute_all_PREs_script.py -i LRE_solution_files_before_PRE_20250124 -o PRE_solution_files_20250124_0.0001_0.1us --PRE_config_file PRE_config_0.0001_0.1us.json
./compute_all_PREs_script.py -i LRE_solution_files_before_PRE_20250124 -o PRE_solution_files_20250124_0.0001_1us --PRE_config_file PRE_config_0.0001_1us.json
./compute_all_PREs_script.py -i LRE_solution_files_before_PRE_20250124 -o PRE_solution_files_20250124_0.0001_1us_parallel --PRE_config_file PRE_config_0.0001_1us_parallel.json


