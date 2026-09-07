"""Tests for adaptive health scoring (E23-T2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agent.health_check import HealthCheckResult
from agent.health_score import compute_health_check_score, no_metrics_score, compute_health_score


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
BASE_START = NOW - timedelta(minutes=30)
BASE_END = NOW
OBS_START = NOW
OBS_END = NOW + timedelta(minutes=15)


def _result(t: datetime, status: int | None, ms: int) -> HealthCheckResult:
    return HealthCheckResult(checked_at=t, status_code=status, response_time_ms=ms)


class TestPrometheusSource:
    def test_metrics_source_is_prometheus(self):
        metrics = {
            "error_rate_base": 0.01, "error_rate_post": 0.01,
            "latency_p99_base_ms": 100.0, "latency_p99_post_ms": 100.0,
            "restarts_base": 0.0, "restarts_post": 0.0,
            "request_rate_base": 10.0, "request_rate_post": 10.0,
        }
        _, _, details = compute_health_score(metrics)
        assert details["metrics_source"] == "prometheus"
        assert details["low_confidence"] is False


class TestHealthCheckSource:
    def test_healthy_service(self):
        results = (
            [_result(BASE_START + timedelta(minutes=i), 200, 50) for i in range(10)]
            + [_result(OBS_START + timedelta(minutes=i), 200, 55) for i in range(10)]
        )
        score, verdict, details = compute_health_check_score(
            results, BASE_START, BASE_END, OBS_START, OBS_END, interval_s=180,
        )
        assert details["metrics_source"] == "health_check"
        assert verdict == "healthy"
        assert score >= 80

    def test_degraded_service_high_error_rate(self):
        base = [_result(BASE_START + timedelta(minutes=i), 200, 50) for i in range(10)]
        post = [_result(OBS_START + timedelta(minutes=i), 200 if i % 2 else 500, 50) for i in range(10)]
        score, verdict, details = compute_health_check_score(
            base + post, BASE_START, BASE_END, OBS_START, OBS_END, interval_s=180,
        )
        # error_rate delta = 0.5 -> clamp(0.5/0.05,0,1)=1.0 -> weighted 40 -> score 60
        assert details["raw_metrics"]["error_rate_post"] == pytest.approx(0.5)
        assert verdict == "degraded"

    def test_failed_service_all_errors_and_slow(self):
        base = [_result(BASE_START + timedelta(minutes=i), 200, 50) for i in range(10)]
        # All errors (delta=1.0 -> 40pt penalty) and 3x response time
        # (ratio=3.0 -> 60pt penalty) -> score 0.
        post = [_result(OBS_START + timedelta(minutes=i), None, 150) for i in range(10)]
        score, verdict, details = compute_health_check_score(
            base + post, BASE_START, BASE_END, OBS_START, OBS_END, interval_s=180,
        )
        assert verdict == "failed"
        assert details["raw_metrics"]["error_rate_post"] == pytest.approx(1.0)

    def test_low_confidence_when_coverage_thin(self):
        # 30-min baseline window, 3-min interval -> ~10 expected pings, only 1 present.
        results = [_result(BASE_START + timedelta(minutes=1), 200, 50)]
        _, _, details = compute_health_check_score(
            results, BASE_START, BASE_END, OBS_START, OBS_END, interval_s=180,
        )
        assert details["low_confidence"] is True
        assert details["coverage"]["post"] == 0.0

    def test_no_results_in_either_window(self):
        score, verdict, details = compute_health_check_score(
            [], BASE_START, BASE_END, OBS_START, OBS_END, interval_s=180,
        )
        # No data -> penalty()'s None-handling gives 0 penalty -> perfect score,
        # but coverage flags it as unreliable.
        assert score == 100
        assert details["low_confidence"] is True
        assert details["raw_metrics"]["samples_base"] == 0
        assert details["raw_metrics"]["samples_post"] == 0


class TestNoMetricsSource:
    def test_returns_null_score_and_unknown_verdict(self):
        score, verdict, details = no_metrics_score("no prometheus, no health check")
        assert score is None
        assert verdict == "unknown"
        assert details["metrics_source"] == "none"
        assert "reason" in details
