import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'disv2.settings')

app = Celery('disv2')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

