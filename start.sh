#! /usr/bin/env bash

# Start the Rucio storage service
docker compose --file rucio/etc/docker/dev/docker-compose.yml --file rucio-compose.override.yml --profile storage up -d
docker exec -it dev_rucio_1 tools/run_tests.sh -i


