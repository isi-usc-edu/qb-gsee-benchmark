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


import gzip
import os
import shutil
from urllib.parse import urlparse

from typing import Any
import logging
import json
import datetime
from pathlib import Path

from jsonschema import validate as _validate
from jsonschema import RefResolver

import requests

import pandas as pd
import numpy as np

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












def clear_or_create_output_directory(output_directory: str) -> None:
    """The `output_directory` will be cleared or created.

    Args:
        output_directory (str): the/relative/path/to/the/output/directory
    """
    try:
        shutil.rmtree(output_directory)
    # except Exception as e:
    #     logging.error(f'Error: {e}', exc_info=True)
    #     logging.error(f"attempted to remove the directory {output_directory}...")
    except:
        pass
    os.mkdir(output_directory)
   











def retrieve_fcidump_from_sftp(url: str, username: str, ppk_path: str, port=22) -> dict:
    filename = os.path.basename(urlparse(url).path)
    _fetch_file_from_sftp(
        url=url, username=username, ppk_path=ppk_path, local_path=filename, port=port
    )
    fcidump_filename = filename.replace(".gz", "")
    with gzip.open(filename, "rb") as f_in:
        with open(fcidump_filename, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    fci = fcidump.read(filename=fcidump_filename)
    os.remove(filename)
    os.remove(fcidump_filename)
    return fci




















def validate_json(
        json_dict: dict,
        schema: dict=None,
        local_resolver_directory: str=None,
    ) -> None:
    """A bespoke utility to validate a JSON object (passed as a `dict`).  
    An error is raised if the `json_dict` is not valid.   Errors should be
    handled accordingly in other scripts.

    Args:
        json_dict (dict): Instance data to validate that must contain the `$schema` field.
    """
    # NOTE: this is making some assumptions about how the schema directory
    # is organized.  It works for our convention.
    if schema is not None:
        if local_resolver_directory is not None:
            # A schema and local resolver directory was provided.
            x = "/TODO_hacky_placeholder_to_fix_local_URL_resolution"
            local_resolver_directory += x
            local_uri = f"file://{os.path.abspath(local_resolver_directory)}"
            resolver = RefResolver(base_uri=local_uri, referrer=schema)
        else:
            raise ValueError(f"`schema` was provided, but no `local_resolver_directory` was provided (need both).")
    else:
        if local_resolver_directory is not None:
            raise ValueError(f"`local_resolver_directory` was provided, but no `schema` was provided (need both).")
        else:
            # no schema provided... fetch it from URL.        
            schema_url = json_dict["$schema"]
            schema = requests.get(schema_url).json()
            base_url = "/".join(schema_url.split("/")[:-1]) + "/"
            resolver = RefResolver(base_uri=base_url, referrer=schema)
    
    _validate(instance=json_dict, schema=schema, resolver=resolver)

    
        
        







def iso8601_timestamp() -> str:
    """Returns the current UTC time as an ISO 8601 formatted string.

    Returns:
        str: The current UTC time in ISO 8601 format.

    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
















def get_latest_ctime_within_dir(search_dir: str) -> float:
    """Recurse through a directory and find the latest file creation time.

    Args:
        search_dir (str): The directory to search through.

    Returns:
        float: The latest creation/change time (`ctime`) for a file.
    """
    latest_ctime = 0
    # this recurses through all subdirectories.
    for root, dirs, files in os.walk(search_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            ctime = os.path.getctime(filepath)
            if ctime > latest_ctime:
                latest_ctime = ctime
    return latest_ctime













def load_json_files(search_dir: str) -> list:
    """Searches through `search_dir` and subdirectories to read in all JSON files.

    Args:
        search_dir (str): relative/path/to/directory

    Returns:
        list: A `list` of Python `dict` objects from each JSON file read in.
    """

    dict_list = []

    # this recurses through all subdirectories.
    for json_file in Path(search_dir).rglob("*.json"):
        with json_file.open("r") as file:
            try:
                data = json.load(file)
                dict_list.append(data)
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                continue # to next json file.
    return dict_list
    


























def data_frame_vlookup(df: pd.DataFrame, 
        lookup_value: Any,
        lookup_value_column_header: str,
        find_value_column_header: str
    ) -> Any:
    """A simple `vlookup` operation for a Pandas `pd.DataFrame`.

    Args:
        df (pd.DataFrame): The `pd.DataFrame` to search within.
        lookup_value (Any): The value to find.
        lookup_value_column_header (str): The column to find `lookup_value` in.
        find_value_column_header (str): The column to locate the corresponding value in.

    Returns:
        Any: The corresponding value in the `find_value_column_header` column.
    """
    assert len(df[df[lookup_value_column_header]==lookup_value]) == 1, \
        f"Found zero or more than one instance of `{lookup_value}` in column `{lookup_value_column_header}`."
    
    return df.loc[df[lookup_value_column_header]==lookup_value, find_value_column_header].values[0]

























def find_dict_with_matching_kv_pair(
        list_of_dicts: list,
        lookup_key: str,
        lookup_val: Any
    ) -> dict:
    """Return a dictionary (from a list of dictionaries) that matches `lookup_key`:`lookup_val` provided.
    If more or less than exactly one dictionary is found in this way and error is raised.

    Args:
        list_of_dicts (list): A list of dictionaries.
        lookup_key (str): The top-level key within the dictionaries to search through.
        lookup_val (Any): The value of the key that we seek.  

    Returns:
        dict: The matching dictionary.
    """

    matching_dicts = [d for d in list_of_dicts if d[lookup_key]==lookup_val]
    assert len(matching_dicts) == 1, \
        f"Found zero or more than one dictionary in list with key:value == {lookup_key}:{lookup_val}."
    return matching_dicts[0]















