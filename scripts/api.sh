#!/usr/bin/env bash
exec uv run --no-sync gunicorn -b 0.0.0.0:5000 -w 4 'api.api:app' --access-logfile=-
