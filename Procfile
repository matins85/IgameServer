release: python3 manage.py migrate
web: daphne igame.asgi:application --port $PORT --bind 0.0.0.0 -v2
# web: gunicorn igame.wsgi --preload --log-file - --log-level debug
# worker: python manage.py runworker --settings=igame.settings -v2
# celery: celery -A igame worker -B -l info
# celery: celery -A igame worker -B -l info --concurrency 2