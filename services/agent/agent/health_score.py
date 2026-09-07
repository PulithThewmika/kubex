"""Health score computation — doc 05 formula (exact).

Penalties (each clamped 0-1):
  error_rate:   clamp((post - base) / 0.05, 0, 1)
  latency_p99:  clamp((post/base - 1.2) / 1.8, 0, 1)
  restarts:     clamp((post - base) / 3.0, 0, 1)

Weights: error_rate=45, latency_p99=30, restarts=25
Score:   clamp(100 - sum(weight * penalty), 0, 100), rounded to int
Verdict: >=80 healthy, 50-79 degraded, <50 failed

Guard rail: if request volume < 0.1 rps in both windows, skip
error/latency penalties and note in details JSONB.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from .config import BASELINE_WINDOW, BASELINE_WINDOW_SECONDS, OBSERVATION_WINDOW, OBSERVATION_WINDOW_SECONDS
from . import promql
from . import health_check

logger = logging.getLogger("kubex.agent.health_score")

WEIGHTS = {
    "error_rate": 45,
    "latency_p99": 30,
    "restarts": 25,
}

# Adaptive weights for services with only an HTTP health check (no Prometheus,
# E23-T2). Reuses the same penalty() curves — response_time via the
# latency_p99 ratio formula, error_rate via the same clamp((post-base)/0.05).
HEALTH_CHECK_WEIGHTS = {
    "response_time": 60,
    "error_rate": 40,
}

LOW_TRAFFIC_THRESHOLD = 0.1  # rps

# A window is "low confidence" if fewer than half its expected health checks
# (window_seconds / health_check_interval_s), or fewer than half its
# expected Prometheus metric values (E23-T4-S10), actually landed in it.
MIN_DATA_COVERAGE = 0.5

# A health check endpoint failing 3 pings in a row (E23-T4-S9) is treated as
# fully down rather than scored by its raw failure fraction — a target that
# dies mid-window would otherwise only ever cost a partial error_rate
# penalty proportional to how late in the window it died.
UNREACHABLE_THRESHOLD = 3


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min_val and max_val."""
    if value < min_val:
        return min_val
    if value > max_val:
        return max_val
    return value


def penalty(base: float | None, post: float | None, kind: str) -> float:
    """Compute 0-1 penalty for a single metric per doc 05.

    Returns 0.0 if either value is None (no data = no penalty).
    """
    if base is None or post is None:
        return 0.0

    if kind == "error_rate":
        delta = post - base
        return clamp(delta / 0.05, 0.0, 1.0)

    elif kind == "latency_p99":
        if base <= 0:
            return 0.0
        ratio = post / base
        return clamp((ratio - 1.2) / 1.8, 0.0, 1.0)

    elif kind == "restarts":
        delta = post - base
        return clamp(delta / 3.0, 0.0, 1.0)

    else:
        raise ValueError(f"Unknown metric kind: {kind}")


def _score_and_verdict(weighted_sum: float) -> tuple[int, str]:
    """Shared score/verdict banding for both the Prometheus and health-check
    formulas — doc 05's >=80 healthy / 50-79 degraded / <50 failed rule is a
    single fixed thing, not one copy per metrics source.
    """
    score = int(round(clamp(100 - weighted_sum, 0, 100)))
    if score >= 80:
        verdict = "healthy"
    elif score >= 50:
        verdict = "degraded"
    else:
        verdict = "failed"
    return score, verdict


def compute_health_score(metrics: dict) -> tuple[int, str, dict]:
    """Compute health score from baseline and observation metrics.

    Args:
        metrics: dict with keys:
            error_rate_base, error_rate_post,
            latency_p99_base_ms, latency_p99_post_ms,
            restarts_base, restarts_post,
            request_rate_base, request_rate_post,
            coverage_base, coverage_post (optional, default 1.0 — fraction of
            the 4 per-component Prometheus queries that returned data rather
            than None; a real scrape gap, not a genuine zero value)

    Returns:
        (score, verdict, details) where:
            score: int 0-100
            verdict: 'healthy' | 'degraded' | 'failed'
            details: dict with per-metric penalties and raw values
    """
    rps_base = metrics.get("request_rate_base")
    rps_post = metrics.get("request_rate_post")
    low_traffic = (
        (rps_base is None or rps_base < LOW_TRAFFIC_THRESHOLD)
        and (rps_post is None or rps_post < LOW_TRAFFIC_THRESHOLD)
    )

    penalties = {}
    skip_reasons = {}

    if low_traffic:
        penalties["error_rate"] = 0.0
        penalties["latency_p99"] = 0.0
        skip_reasons["error_rate"] = "low traffic (<0.1 rps in both windows)"
        skip_reasons["latency_p99"] = "low traffic (<0.1 rps in both windows)"
    else:
        penalties["error_rate"] = penalty(
            metrics.get("error_rate_base"),
            metrics.get("error_rate_post"),
            "error_rate",
        )
        penalties["latency_p99"] = penalty(
            metrics.get("latency_p99_base_ms"),
            metrics.get("latency_p99_post_ms"),
            "latency_p99",
        )

    penalties["restarts"] = penalty(
        metrics.get("restarts_base"),
        metrics.get("restarts_post"),
        "restarts",
    )

    weighted_sum = sum(WEIGHTS[k] * penalties[k] for k in WEIGHTS)
    score, verdict = _score_and_verdict(weighted_sum)

    coverage_base = metrics.get("coverage_base", 1.0)
    coverage_post = metrics.get("coverage_post", 1.0)
    data_gap = coverage_base < MIN_DATA_COVERAGE or coverage_post < MIN_DATA_COVERAGE

    details = {
        "metrics_source": "prometheus",
        "penalties": {k: round(v, 4) for k, v in penalties.items()},
        "weights": WEIGHTS,
        "weighted_sum": round(weighted_sum, 2),
        "low_traffic": low_traffic,
        "data_gap": data_gap,
        "low_confidence": low_traffic or data_gap,
        "coverage": {"base": round(coverage_base, 2), "post": round(coverage_post, 2)},
        "raw_metrics": {
            "error_rate_base": metrics.get("error_rate_base"),
            "error_rate_post": metrics.get("error_rate_post"),
            "latency_p99_base_ms": metrics.get("latency_p99_base_ms"),
            "latency_p99_post_ms": metrics.get("latency_p99_post_ms"),
            "restarts_base": metrics.get("restarts_base"),
            "restarts_post": metrics.get("restarts_post"),
            "request_rate_base": rps_base,
            "request_rate_post": rps_post,
        },
    }
    if skip_reasons:
        details["skip_reasons"] = skip_reasons

    return score, verdict, details


def _ping_failed(result) -> bool:
    """A single health check ping counts as failed: unreachable, or an
    HTTP error status. Shared by _http_error_rate and
    _trailing_consecutive_failures so the two stay in sync — they're
    supposed to measure the same "failed" concept."""
    return result.status_code is None or result.status_code >= 400


def _http_error_rate(results: list) -> float | None:
    """Fraction of health check pings that failed (status >= 400 or unreachable)."""
    if not results:
        return None
    errors = sum(1 for r in results if _ping_failed(r))
    return errors / len(results)


def _avg_response_time(results: list) -> float | None:
    if not results:
        return None
    return sum(r.response_time_ms for r in results) / len(results)


def _trailing_consecutive_failures(results: list) -> int:
    """Count failed pings at the tail of results (oldest-first), i.e. the
    most recent run of consecutive failures."""
    count = 0
    for r in reversed(results):
        if _ping_failed(r):
            count += 1
        else:
            break
    return count


def compute_health_check_score(
    results: list,
    baseline_start: datetime,
    baseline_end: datetime,
    observation_start: datetime,
    observation_end: datetime,
    interval_s: int,
) -> tuple[int, str, dict]:
    """Adaptive score for services with only an HTTP health check (E23-T2).

    Weights: response_time=60, error_rate=40 (vs the Prometheus formula's
    error_rate=45/latency=30/restarts=25) — there's no restart signal
    without Kubernetes/Prometheus visibility.
    """
    base_results = [r for r in results if baseline_start <= r.checked_at < baseline_end]
    post_results = [r for r in results if observation_start <= r.checked_at <= observation_end]

    response_time_base = _avg_response_time(base_results)
    response_time_post = _avg_response_time(post_results)
    error_rate_base = _http_error_rate(base_results)
    error_rate_post = _http_error_rate(post_results)

    # A target that's gone fully unreachable is worse than its raw
    # error_rate over the window implies (it may have died partway through)
    # — score it as 100% failed for the rest of the window instead. Checked
    # in both windows: a target already dead for the tail of baseline must
    # not keep a partial baseline error_rate that understates how broken it
    # already was pre-deploy.
    unreachable_base = _trailing_consecutive_failures(base_results) >= UNREACHABLE_THRESHOLD
    unreachable_post = _trailing_consecutive_failures(post_results) >= UNREACHABLE_THRESHOLD
    if unreachable_base:
        error_rate_base = 1.0
    if unreachable_post:
        error_rate_post = 1.0
    unreachable = unreachable_base or unreachable_post

    penalties = {
        "response_time": penalty(response_time_base, response_time_post, "latency_p99"),
        "error_rate": penalty(error_rate_base, error_rate_post, "error_rate"),
    }

    weighted_sum = sum(HEALTH_CHECK_WEIGHTS[k] * penalties[k] for k in HEALTH_CHECK_WEIGHTS)
    score, verdict = _score_and_verdict(weighted_sum)

    expected_base = max((baseline_end - baseline_start).total_seconds() / interval_s, 1.0)
    expected_post = max((observation_end - observation_start).total_seconds() / interval_s, 1.0)
    coverage_base = min(len(base_results) / expected_base, 1.0)
    coverage_post = min(len(post_results) / expected_post, 1.0)
    low_confidence = coverage_base < MIN_DATA_COVERAGE or coverage_post < MIN_DATA_COVERAGE

    details = {
        "metrics_source": "health_check",
        "penalties": {k: round(v, 4) for k, v in penalties.items()},
        "weights": HEALTH_CHECK_WEIGHTS,
        "weighted_sum": round(weighted_sum, 2),
        "low_confidence": low_confidence,
        "unreachable": unreachable,
        "unreachable_base": unreachable_base,
        "unreachable_post": unreachable_post,
        "coverage": {"base": round(coverage_base, 2), "post": round(coverage_post, 2)},
        "raw_metrics": {
            "response_time_base_ms": response_time_base,
            "response_time_post_ms": response_time_post,
            "error_rate_base": error_rate_base,
            "error_rate_post": error_rate_post,
            "samples_base": len(base_results),
            "samples_post": len(post_results),
        },
    }

    return score, verdict, details


def no_metrics_score(reason: str) -> tuple[None, str, dict]:
    """No Prometheus and no health check configured — can't score this deployment."""
    return None, "unknown", {"metrics_source": "none", "reason": reason, "raw_metrics": {}}


def _max_of(values: list[float | None]) -> float | None:
    """Return the max of non-None values, or None if all are None."""
    valid = [v for v in values if v is not None]
    return max(valid) if valid else None


def _sum_of(values: list[float | None]) -> float | None:
    """Return the sum of non-None values, or None if all are None."""
    valid = [v for v in values if v is not None]
    return sum(valid) if valid else None


async def _query_component(
    component: str, namespace: str, window: str, timestamp: datetime
) -> dict:
    """Query all metrics for a single Prometheus component."""
    return {
        "error_rate": await promql.query_error_rate(component, namespace, window, timestamp),
        "latency_p99": await promql.query_latency_p99(component, namespace, window, timestamp),
        "restarts": await promql.query_restarts(component, namespace, window, timestamp),
        "request_rate": await promql.query_request_rate(component, namespace, window, timestamp),
    }


def _coverage(results: list[dict]) -> float:
    """Fraction of components whose "restarts" query returned actual data
    (E23-T4-S10) — the one metric here that isn't itself ambiguous with
    "no data": error_rate (0/0 division) and latency_p99
    (histogram_quantile over no buckets) both legitimately return None on
    a genuinely quiet window per the project's own
    Prometheus-unreachable-vs-low-traffic gotcha, and request_rate can
    equally be None the first time a component has never taken traffic.
    restarts comes from kube_pod_container_status_restarts_total via
    kube-state-metrics, unrelated to application traffic, so a None there
    reflects a real scrape gap (Prometheus down, target unreachable) rather
    than the service simply being idle."""
    if not results:
        return 0.0
    present = sum(1 for r in results if r["restarts"] is not None)
    return present / len(results)


async def _aggregate_metrics(
    components: list[str], namespace: str, window: str, timestamp: datetime
) -> dict:
    """Query each component and aggregate: max for rates/latency, sum for restarts/rps."""
    results = [
        await _query_component(comp, namespace, window, timestamp)
        for comp in components
    ]
    return {
        "error_rate": _max_of([r["error_rate"] for r in results]),
        "latency_p99": _max_of([r["latency_p99"] for r in results]),
        "restarts": _sum_of([r["restarts"] for r in results]),
        "request_rate": _sum_of([r["request_rate"] for r in results]),
        "coverage": _coverage(results),
    }


async def assess_deployment(
    session: AsyncSession,
    deployment,
    components: list[str],
    namespace: str,
    prometheus_available: bool = True,
    health_check_url: str | None = None,
    health_check_interval_s: int = 30,
) -> tuple[int | None, str, dict] | None:
    """Fetch metrics for both windows, compute health score, and write to DB.

    Picks the metrics source adaptively (E23-T2): Prometheus when the
    service's cluster reports it reachable, else an HTTP health check
    fallback if one is configured, else no score at all.

    Args:
        session: async SQLAlchemy session
        deployment: Deployment ORM instance (must have finished_at set)
        components: list of Prometheus service labels to query and aggregate
        namespace: Kubernetes namespace
        prometheus_available: False when the service's cluster reports
            prometheus_status != 'found' (remote cluster-agent path)
        health_check_url: fallback HTTP health check URL, if configured
        health_check_interval_s: ping interval backing the ring buffer

    Returns:
        (score, verdict, details) tuple, or None if deployment can't be assessed
    """
    if deployment.finished_at is None:
        logger.warning("Deployment %d has no finished_at, skipping", deployment.id)
        return None

    baseline_start = deployment.finished_at - timedelta(seconds=BASELINE_WINDOW_SECONDS)
    baseline_end = deployment.finished_at
    observation_start = deployment.finished_at
    observation_end = deployment.finished_at + timedelta(seconds=OBSERVATION_WINDOW_SECONDS)

    if prometheus_available:
        logger.info(
            "Assessing deployment %d for components %s: baseline window %s before %s, "
            "observation window %s after deployment",
            deployment.id, components, BASELINE_WINDOW,
            baseline_end.isoformat(), OBSERVATION_WINDOW,
        )

        base = await _aggregate_metrics(components, namespace, BASELINE_WINDOW, baseline_end)
        post = await _aggregate_metrics(components, namespace, OBSERVATION_WINDOW, observation_end)

        metrics = {
            "error_rate_base": base["error_rate"],
            "error_rate_post": post["error_rate"],
            "latency_p99_base_ms": base["latency_p99"],
            "latency_p99_post_ms": post["latency_p99"],
            "restarts_base": base["restarts"],
            "restarts_post": post["restarts"],
            "request_rate_base": base["request_rate"],
            "request_rate_post": post["request_rate"],
            "coverage_base": base["coverage"],
            "coverage_post": post["coverage"],
        }

        score, verdict, details = compute_health_score(metrics)
        details["components"] = components

    elif health_check_url:
        logger.info(
            "Prometheus unavailable for deployment %d, scoring via health check %s",
            deployment.id, health_check_url,
        )
        results = health_check.get_results(deployment.service_id)
        score, verdict, details = compute_health_check_score(
            results, baseline_start, baseline_end, observation_start, observation_end,
            health_check_interval_s,
        )

    else:
        logger.info(
            "No Prometheus or health check available for deployment %d, skipping scoring",
            deployment.id,
        )
        score, verdict, details = no_metrics_score(
            "no Prometheus (cluster unreachable) and no health_check_url configured"
        )

    logger.info(
        "Deployment %d scored %s — verdict: %s",
        deployment.id, score if score is not None else "n/a", verdict,
    )

    return score, verdict, details
