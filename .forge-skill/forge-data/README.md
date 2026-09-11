# Forge Data

This directory is the source-tree development location for Forge-generated
data. Installed Forge deployments resolve the same layout beside the physical
`forge` directory, for example `E:\\CodexHome\\forge-data`.

Data is partitioned by project ID and Skill. Runtime state must not be
committed or copied into a project repository.

`runtime.json` is the only tracked machine-local configuration file here. It
contains the host Python executable and direct-collection timeout; it must not
contain credentials. Project-owned configuration remains under the project's
`.forge-skill/learning/` directory.
