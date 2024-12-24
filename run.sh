#!/bin/bash

# Start Redis if not running (uncomment if needed)
# redis-server &

# Start Flask
flask run &

# Start Celery worker
celery -A app.tasks.celery_app.celery worker --loglevel=INFO -P solo

# Wait for all background processes
wait
