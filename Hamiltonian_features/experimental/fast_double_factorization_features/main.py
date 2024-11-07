#!/usr/bin/env python3



"""

Example usage from an FCIDUMP file

"""

import argparse
import logging



import datetime


from json_to_ham_features_csv import compute_ham_features_csv





def main(args):
    
    if args.verbose:
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        file_handler = logging.FileHandler(args.log_file, mode="a") # mode "a" for append.
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handlers = [console_handler , file_handler]
        for h in handlers:
            h.setFormatter(formatter)
            logger.addHandler(h)


        start_time = datetime.datetime.now()
        logging.info(f"===============================================")
        logging.info(f"start time: {start_time}")
        logging.info(f"input file: {args.input}")
        logging.info(f"output file: {args.output}")
        logging.info(f"verbose logging enabled.")
        
        

    
    ham_features_dict = compute_ham_features_csv(
        filename=args.input,
        save=True,
        csv_filename=args.output,
        verbose_logging=args.verbose
    )

    if args.verbose:
        stop_time = datetime.datetime.now()
        logging.info(f"done.")
        logging.info(f"start time: {start_time}")
        logging.info(f"stop time: {stop_time}")
        logging.info(f"run time (seconds): {(stop_time - start_time).total_seconds()}")

    
    








if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate the features of a Hamiltonian (in FCIDUMP format)"
    )
    parser.add_argument(
        "-i", 
        "--input",
        type=str,
        required=True,
        help="input FCIDUMP file name"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="output features CSV file name"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="provide verbose output"
    )
    parser.add_argument(
        "--log_file",
        type=str,
        required=False,
        default="log.txt",
        help="log file that verbose output is appended to."
    )
    args = parser.parse_args()
    main(args)

    
