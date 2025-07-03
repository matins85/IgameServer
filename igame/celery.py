import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'igame.settings')

app = Celery('igame')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery beat schedule for game session management
app.conf.beat_schedule = {
    'game-session-manager': {
        'task': 'game_lobby.tasks.game_session_manager',
        'schedule': 1.0,  # Run every second
    },
}

app.conf.timezone = 'UTC'
