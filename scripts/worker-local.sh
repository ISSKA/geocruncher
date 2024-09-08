#!/usr/bin/env bash
watchmedo auto-restart --directory=./ --pattern=*.py --recursive -- celery -A api worker -l INFO -Q geocruncher:long_running,geocruncher:priority
