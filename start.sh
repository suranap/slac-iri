#! /usr/bin/env bash

# Create a shared network to connect all services
is_network=$(docker network ls --format json | jq -r 'select(.Name == "iri-shared") | .Name')
if [ -z "$is_network" ]; then
    docker network create iri-shared
fi

# Start the Rucio storage service
docker compose --file rucio/etc/docker/dev/docker-compose.yml --file rucio-compose.override.yml --profile storage up -d
docker exec -it dev_rucio_1 tools/run_tests.sh -i

# Start the Slurm service
docker compose --file slurm/docker-compose.yml up -d

# Verify the Slurm service is running. Get the SLURM_JWT token. Notice it is set to infinite lifespan, insecure.
export $(docker compose --file slurm/docker-compose.yml exec slurmrestd scontrol token lifespan=infinite)
curl -k -H X-SLURM-USER-TOKEN:${SLURM_JWT} -H X-SLURM-USER-NAME:root -X GET 'http://localhost:9200/slurm/v0.0.41/diag' -o /dev/null -s -w "%{http_code}"

# Start the PSI/J service. Note this requires SLURM_JWT to be set.
docker compose --file psijd/docker-compose.yml up -d 

# Verify the PSI/J service is running
curl 'http://127.0.0.1:10050/hello'

