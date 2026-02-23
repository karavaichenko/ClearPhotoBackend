from celery import Celery
import os

# Создаем экземпляр Celery
celery_app = Celery(
    'tasks',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6380/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6380/0')
)

# Настройки Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут
    task_soft_time_limit=25 * 60,  # 25 минут
    task_ignore_result=False,  # Не игнорировать результаты
    result_expires=3600,  # Результаты хранятся 1 час
)

# Автоматически находим задачи
celery_app.autodiscover_tasks(['src.ml.tasks'])