################################################################################
# © Copyright 2024 Zapata Computing Inc.
################################################################################

import gzip
import os
import shutil
from urllib.parse import urlparse

import paramiko
from pyscf.tools import fcidump


def _fetch_file_from_sftp(
    url: str, local_path: str, ppk_path: str, username: str, port=22
):

    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    remote_path = parsed_url.path.lstrip("/")

    with paramiko.SSHClient() as client:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=hostname,
            port=port,
            username=username,
            key_filename=ppk_path,
        )

        with client.open_sftp() as sftp:
            print(f"Downloading {remote_path} to {local_path}...")
            sftp.get(remote_path, local_path)


def retrieve_fcidump_from_sftp(url: str, username: str, ppk_path: str, port=22) -> dict:
    filename = os.path.basename(urlparse(url).path)
    _fetch_file_from_sftp(
        url=url, username=username, ppk_path=ppk_path, local_path=filename, port=port
    )
    fcidump_filename = filename.replace(".gz", "")
    with gzip.open(filename, "rb") as f_in:
        with open(fcidump_filename, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    return fcidump.read(filename=fcidump_filename)
