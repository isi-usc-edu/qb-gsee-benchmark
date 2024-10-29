# JSON File Schemas

### What is it?

A reasonably extensible JSON file format for `problem_instance` files (and other files).

### So what is it?

A JSON file that contains a lot of metadata about a `problem_instance`, including the run time and accuracy requirements that a benchmark performer needs to achieve.  

### Where is the data?

The data files may be large, so typically the JSON file only contains the metadata and *URLs* to where the data files may be downloaded.

###  How do I download the associated data files (e.g., Hamiltonians)?

Each `problem_instance` file may point to data sets on different servers, so you'll need to contact the POCs referenced in each `problem_instance` file.  

For the current set of GSEE `problem_instances` provided, the data lives on an SFTP server at [sftp.l3harris.com](sftp://sftp.l3harris.com).  The *read-only* credentials for accessing the Hamiltonian files are available on the QB program basecamp here: [https://3.basecamp.com/3613864/buckets/26823103/messages/7222735635](https://3.basecamp.com/3613864/buckets/26823103/messages/7222735635).

###  What if the JSON schema doesn't have the fields I want to use?

Contact the team and we'll discuss modifying the schema.
