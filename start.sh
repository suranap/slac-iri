#! /usr/bin/env bash

# Start the Rucio storage service
docker compose --file rucio/etc/docker/dev/docker-compose.yml --file rucio-compose.override.yml --profile storage up -d
docker exec -it dev_rucio_1 tools/run_tests.sh -i

# Start the Slurm service
docker compose --file slurm/docker-compose.yml up -d

# Verify the Slurm service is running
export $(docker compose --file slurm/docker-compose.yml exec slurmrestd scontrol token)
curl -k -vvvv -H X-SLURM-USER-TOKEN:${SLURM_JWT} -H X-SLURM-USER-NAME:root -X GET 'http://localhost:9200/slurm/v0.0.41/diag' 
