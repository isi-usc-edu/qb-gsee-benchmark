#!/usr/bin/env python3

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

import sys
import os
from urllib.parse import urlparse
import logging
logging.basicConfig(level=logging.INFO)



# Check to see if you have the key material for the SFTP server:
if not os.path.exists("darpa-qb-key.pem"):
    logging.error(f"Missing SFTP key file for this example script.")
    logging.error(f"Did you run the `get_sftp_key.py` script?")
    sys.exit(1)
    





# Assuming you have installed qb_gsee_benchmark per the README,
# you may import/use this function:
from qb_gsee_benchmark.utils import fetch_file_from_sftp



# This URL is from one `problem_instance.json` file:
url = "sftp://sftp.l3harris.com/gsee/FCIDUMP_benzene_sto-3g_4c655f65-1899-469c-975a-a3caec750697.gz"


# Here we copy the last part of the URL to use as the local file name.
# You may use another naming convention in your script.
local_path = urlparse(url).path.split("/")[-1] 




# Fetch the file:
fetch_file_from_sftp(
    url=url,
    local_path=local_path,
    ppk_path="darpa-qb-key.pem", # <-- .pem file in the /examples directory.
    username="darpa-qb" # <-- this username is tied to the .pem file.
)



logging.info(f"fetched {local_path} from SFTP server.")

