#!/usr/bin/env bash
gunicorn -b localhost:5000 -w 4 'api.api:app' --access-logfile=-
