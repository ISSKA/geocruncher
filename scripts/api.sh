#!/usr/bin/env bash
gunicorn -w 4 'api.api:app' --access-logfile=-
