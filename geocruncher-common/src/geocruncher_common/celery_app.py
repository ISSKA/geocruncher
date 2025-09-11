from celery import Celery

app = Celery('geocruncher')
app.config_from_object('geocruncher_common.celeryconfig')

