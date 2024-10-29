# qb-file-schemas

Proposed JSON schemas for Quantum Benchmarking file exchange.  This repository contains *only* the schemas.  
The actual `problem_instance` files are in a few other places:

1. Ground State Energy Estimation (GSEE):  https://github.com/zapatacomputing/qb-gsee-benchmark/tree/main/instances/schemas
2. Differential Equations:  TBD
3. Quantum Dynamics:  TBD

### What is it?

A reasonably extensible JSON file format for `problem_instance` files.

### So what is it?

A JSON file that contains a lot of metadata about a `problem_instance`, including the run time and accuracy requirements that a benchmark performer needs to achieve.  

### Where is the data?

The data files may be large, so typically the JSON file only contains the metadata and *URLs* to where the data files may be downloaded.

###  How do I download the associated data files (e.g., Hamiltonians)?

Each `problem_instance` file may point to data sets on different servers, so you'll need to contact the POCs referenced in each `problem_instance` file.  

For the current set of GSEE `problem_instances` provided by the BOBQAT team, the data lives on an SFTP server at sftp.l3harris.com.  The *read-only* credentials for accessing the Hamiltonian files are available on the QB program basecamp here XXX_insert_link_XXX.

###  How do I submit a new `problem_instance` file?

Develop your own `problem_instance` JSON file, filling in most of the self-explanatory fields and generating *new* UUIDs for your instance and associated files.  

When developing a new `problem_instance` file, Microsoft VS code will usually automatically pull the schemas and to give you hints on what fields are required and the associated format.  Restart VS Code or use the `JSON: Clear Schema Cache` action to update schemas.  If this continues to fail, VS Code users can manually download schemas and manually associate a schema with a filename by regex.  There are a variety of other tools for validating your JSON file.

The `problem_instance` JSON metadata file should be placed in the appropriate repository. E.g., for GSEE: https://github.com/zapatacomputing/qb-gsee-benchmark/tree/main/instances/schemas.  

The associated data files that go along with your `problem_instance` file will be placed somewhere else.  If you don't have your own server, L3Harris can host your files on the SFTP server.  L3Harris has additional *read/write* credentials for the SFTP server that may be shared with other teams.

Note that the schema includes a field for `license`, so you may choose the appropriate license for your `problem_instance` and related data.

###  What if the JSON schema doesn't have the fields I want to use?

Contact the BOBQAT team and we'll discuss modifying the schema.
