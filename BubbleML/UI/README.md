# Bubble ML

## Description

Bubble ML is an interactive GUI to explore various *latent spaces* of the Hamiltonians
included in the benchmark and see how different solvers are performing againts those 
Hamiltonians.

## Prerequisites:

1. Instal the `qb_gsee_benchmark` package per the instructions 
in the main [`README.md`](../../README.md).  This will install all the necessary
Python packages.
2. Ubuntu/Debian users must `sudo apt install python3-pyqt5`.

## Data input:

Current solution: Filter [`data.csv`](../../standard_report/data.csv) down to
only one solver (filter rows).  Then load that data through the Bubble ML load option.

TODO: Future solution: Have Bubble ML load `data.csv` and give the user an option
to select which solver they want to analyze.

## How to interact with Bubble ML

Launch the GUI: `./main.py` or `python3 main.py`.

TODO: some explanation of how a user will interact with it.