#!/usr/bin/env bash
docker compose -p geocruncher -f docker/geocruncher.docker-compose.yaml up --build --remove-orphans
