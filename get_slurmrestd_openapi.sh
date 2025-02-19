#!/usr/bin/env bash

# Get the Slurm REST API OpenAPI specification
docker exec slurmrestd su rest -c 'slurmrestd --generate-openapi-spec -d 0.0.41' > slurm/slurmrestd_openapi.json

# Generate the Python client
mkdir -p slurm/slurmrestd_client
docker run --rm -v $PWD:/local openapitools/openapi-generator-cli generate -i /local/slurm/slurmrestd_openapi.json -g python -o /local/slurm/slurmrestd_client --additional-properties=packageName=slurmrestd_client

# Install the client (PyLance doesn't see it when installed in editable mode -e)
pip install ./slurm/slurmrestd_client
