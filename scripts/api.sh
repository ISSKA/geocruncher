#!/usr/bin/env bash

# Use port 5000 in prod and 5001 in dev
PORT=$([ "$DEV" == "1" ] && echo "5001" || echo "5000")
gunicorn -b localhost:$PORT -w 4 'api.api:app' --access-logfile=-
