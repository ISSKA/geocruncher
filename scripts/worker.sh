#!/usr/bin/env bash
celery -A api worker -l INFO -Q geocruncher:long_running,geocruncher:priority
# TODO: second worker just for the priority queue
# Think about concurrency, memory limits, autoscale
# https://docs.celeryq.dev/en/stable/userguide/workers.html#max-memory-per-child-setting
# celery -A api worker -l INFO -Q geocruncher:priority
