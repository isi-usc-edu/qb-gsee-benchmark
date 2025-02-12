# Examples

## Accessing FCIDUMP files on the SFTP server

1. We want to share the *READ-ONLY* key to access the SFTP server with a wide audience, but don't want to share it as searchable plain text in Github.  The solution to this is to share the `obfuscated_sftp_server_key.bin` file and provide the [`get_sftp_key.py`](get_sftp_key.py) script.  Running the [`get_sftp_key.py`](get_sftp_key.py) script will write out `darpa-qb-key.pem` for use.  The username associated with this key is `darpa-qb`.  Contact the team at [`bobqat@l3harris.com`](mailto:bobqat@l3harris.com) if you need a read/write account.
2. The [`fetch_file_from_sftp_server.py`](fetch_file_from_sftp_server.py) script give a very brief example of downloading on FCIDUMP file from the SFTP server using the key and associated username.
3. The motivated user may also use FileZilla, WinSCP, or some other GUI-based file transfer utility program to access the files.  (Converting the `.pem` key to `.ppk` format may be required depending on the file transfer utility.)

## Validating JSON files

1. The `problem_instance`, `solution_files` and other files are JSON and adhere to their schemas.  Please validate any new files that are contributed.  The [`validate_json_files.py`](validate_json_files.py) provides an example to validate `problem_instance` and `solution` files.  The script may be modified to validate other JSON files.

## DMRG examples

1. [`run_dmrg.ipynb`](run_dmrg.ipynb)
2. [`run_support.py`](run_support.py)
3. [`get_overlap.ipynb`](get_overlap.ipynb)


