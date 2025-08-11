import os

broker_url = f"redis://{os.environ['REDIS_HOST']}:6379/1"
result_backend = f"redis://{os.environ['REDIS_HOST']}:6379/2"
imports = ('api.tasks')
# Task hard time limit in seconds. Set to 6 hours
task_time_limit = 6 * 60 * 60
# Time after which the results are automatically deleted in seconds. Set to 8 hours
# TODO: also delete associated data
result_expires = 8 * 60 * 60
# disable prefetching, since we have long running tasks
# WARNING: changing this will break the job cancellation system
worker_prefetch_multiplier = 1
task_default_queue = 'geocruncher:long_running'
task_routes = {
    'api.tasks.compute_intersections': 'geocruncher:priority',
}
broker_connection_retry_on_startup = True
task_track_started = True
task_send_sent_event = True
worker_send_task_events = True
