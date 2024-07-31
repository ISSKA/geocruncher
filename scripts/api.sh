#!/usr/bin/env bash
gunicorn -w 4 'geocruncher-api.api:app' --access-logfile=-
