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


import random
random.seed(42)
pad_length = 512
pad = random.randbytes(pad_length)


# Open/read obfuscated key file:
with open("obfuscated_sftp_server_key.bin", "rb") as f:
    obfuscated_key = f.read()

# Deobfuscate key bytes:
plain_text_key = bytearray(len(obfuscated_key))
for i in range(len(obfuscated_key)):
    plain_text_key[i] = obfuscated_key[i]^pad[i%pad_length]

# Write out plain-text key file:
key_file_name = "darpa-qb-key.pem"
with open(key_file_name, "wb") as f:
    f.write(plain_text_key)


print(f"SFTP server key `{key_file_name}` is now available for use.")


