import os
from celery import Celery
from app.config import REDIS_URL

celery_app = Celery(
    "maintai_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Tests : les tâches s'exécutent directement dans le processus (pas besoin de worker)
if os.getenv("CELERY_TASK_ALWAYS_EAGER") == "1":
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)
