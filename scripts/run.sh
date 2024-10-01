#!/usr/bin/env bash
# This script allows running Geocruncher in local development mode
# Docker containers use the code on disk, and both the api and worker are setup to hot reload
set -e
DOCKER_BUILDKIT=1 docker compose -p geocruncher-local -f docker/local.docker-compose.yaml up --build --remove-orphans
