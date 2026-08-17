from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()
settings.validate_runtime_secrets()
celery_app = Celery("tenantflow", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "tenantflow.webhooks.*": {"queue": "webhooks"},
        "tenantflow.maintenance.*": {"queue": "maintenance"},
    },
    beat_schedule={
        "cleanup-expired-state-hourly": {
            "task": "tenantflow.maintenance.cleanup_expired",
            "schedule": crontab(minute=17),
        }
    },
)
celery_app.autodiscover_tasks(["app.workers"])
