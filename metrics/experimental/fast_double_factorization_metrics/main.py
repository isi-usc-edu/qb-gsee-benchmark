"""

Example usage from an FCIDUMP file

"""
from json_to_metrics_csv import compute_metrics_csv
from pyscf.tools import fcidump



if __name__ == "__main__":
    filename = 'test.FCIDUMP'
    data = fcidump.read(filename)

    metrics = compute_metrics_csv(filename=filename, save=False)
    print(metrics)


