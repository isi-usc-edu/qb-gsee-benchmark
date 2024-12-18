notes:

Test run setting `LRE_config_overlaps.json` parameter  `max_orbitals` to 1000 (more than we need.)  Calculation started over the largest problem instance (below).  Calculation ran for over a day and errored out.


Problem instance "Sc_1" as 3 tasks

task UUID, num_orbitals

10119019-eea2-45c9-a748-e206780c4235,   135 orbitals, we have overlap
ca6f7678-0952-4fe4-83fe-c4455a682132,   54 orbitals, we have overlap
78d5e5ba-0b2c-4cfe-92c5-f1c749150015,   88  orbitals, we have overlap


testing call:

nohup ./compute_all_LREs_script.py -i ./testing_LRE/problem_instances/ -o ./testing_LRE/temp_LRE_solution_files/ --LRE_config_file LRE_config_overlaps.json --sftp_username darpa-qb --sftp_key_file ~/.ssh/darpa-qb-key.ppk &





