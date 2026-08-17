from __future__ import annotations

import logging

from prometheus_client import Counter, Gauge, Histogram

from app.infra.redis import get_redis

logger = logging.getLogger(__name__)

HTTP_REQUESTS = Counter(
    "tenantflow_http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "tenantflow_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
)
RATE_LIMIT_REJECTIONS = Counter(
    "tenantflow_rate_limit_rejections_total",
    "Rate-limit rejections",
    ["scope"],
)
STRIPE_WEBHOOK_EVENTS = Counter(
    "tenantflow_stripe_webhook_events_total",
    "Stripe webhook event outcomes",
    ["outcome"],
)

# Celery workers run in separate OS processes. Worker outcomes are accumulated atomically in Redis
# and projected into gauges at scrape time, so `/metrics` remains correct across worker processes.
BACKGROUND_JOB_OUTCOMES = Gauge(
    "tenantflow_background_job_outcomes",
    "Cumulative background job outcomes recorded in Redis",
    ["job", "outcome"],
)
WEBHOOK_DELIVERY_OUTCOMES = Gauge(
    "tenantflow_webhook_delivery_outcomes",
    "Cumulative outbound webhook outcomes recorded in Redis",
    ["outcome"],
)

_BACKGROUND_HASH = "tenantflow:metrics:background_jobs"
_WEBHOOK_HASH = "tenantflow:metrics:webhook_deliveries"

_BACKGROUND_LABELS = {
    ("invitation_email", "success"),
    ("invitation_email", "skipped"),
    ("invitation_email", "retry"),
    ("cleanup", "success"),
    ("cleanup", "retry"),
    ("webhook_delivery", "success"),
    ("webhook_delivery", "retry"),
    ("webhook_delivery", "dead"),
    ("webhook_delivery", "skipped"),
}
_WEBHOOK_LABELS = {"delivered", "retry", "dead", "skipped"}


async def record_background_job(job: str, outcome: str) -> None:
    """Atomically record a low-cardinality Celery outcome in Redis."""
    from redis.exceptions import RedisError

    client = await get_redis()
    try:
        await client.hincrby(_BACKGROUND_HASH, f"{job}:{outcome}", 1)
    except (RedisError, OSError) as exc:
        logger.warning("background_metric_record_failed job=%s outcome=%s error=%s", job, outcome, exc)
    finally:
        await client.aclose()


async def record_webhook_delivery(outcome: str) -> None:
    """Atomically record a low-cardinality outbound webhook outcome in Redis."""
    from redis.exceptions import RedisError

    client = await get_redis()
    try:
        await client.hincrby(_WEBHOOK_HASH, outcome, 1)
    except (RedisError, OSError) as exc:
        logger.warning("webhook_metric_record_failed outcome=%s error=%s", outcome, exc)
    finally:
        await client.aclose()


async def refresh_distributed_metrics() -> None:
    """Refresh worker-produced metrics before Prometheus serializes the API registry."""
    from redis.exceptions import RedisError

    client = await get_redis()
    try:
        background = await client.hgetall(_BACKGROUND_HASH)
        webhook = await client.hgetall(_WEBHOOK_HASH)
    except (RedisError, OSError) as exc:
        logger.warning("distributed_metric_refresh_failed error=%s", exc)
        return
    finally:
        await client.aclose()

    for job, outcome in _BACKGROUND_LABELS:
        value = int(background.get(f"{job}:{outcome}", 0))
        BACKGROUND_JOB_OUTCOMES.labels(job=job, outcome=outcome).set(value)
    for outcome in _WEBHOOK_LABELS:
        WEBHOOK_DELIVERY_OUTCOMES.labels(outcome=outcome).set(int(webhook.get(outcome, 0)))
