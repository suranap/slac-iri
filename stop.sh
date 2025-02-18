#! /usr/bin/env bash

# Start the Rucio storage service
docker compose --file rucio/etc/docker/dev/docker-compose.yml --file rucio-compose.override.yml --profile storage down -v
