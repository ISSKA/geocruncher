#!/usr/bin/env bash
gunicorn -b 0.0.0.0:5000 -w 4 'api.api:app' --access-logfile=-
