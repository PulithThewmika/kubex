"""Guard: every SQL query in a customer-facing (embeddable) Grafana
dashboard must be org-scoped, so a future panel can't silently
reintroduce the cross-tenant leak fixed in #833.

Scans deploy/grafana/dashboards/customer/ — the set the panel proxy's
EMBEDDABLE_DASHBOARD_UIDS allows and that #834 split off from the
operator-only platform-wide dashboards.
"""

import json
from pathlib import Path

import pytest

_CUSTOMER_DIR = (
    Path(__file__).resolve().parents[3] / "deploy" / "grafana" / "dashboards" / "customer"
)
CUSTOMER_FACING = sorted(p.name for p in _CUSTOMER_DIR.glob("*.json"))

# A DORA panel is org-scoped by calling the dora_*(p_org_id) function
# rather than reading the same-named NULL-org view (CLAUDE.md decision 6).
_DORA_NAMES = ("dora_deploy_frequency", "dora_lead_time", "dora_change_failure_rate", "dora_mttr")

# Tables that carry org_id (CLAUDE.md decision 9).
ORG_SCOPED_TABLES = ("services", "deployments", "alerts", "pipeline_events", "health_assessments")


def _load(filename: str) -> dict:
    return json.loads((_CUSTOMER_DIR / filename).read_text())


def _sql_targets(dashboard: dict):
    for panel in dashboard.get("panels", []):
        for target in panel.get("targets", []):
            if target.get("rawSql"):
                yield f"panel {panel.get('id')}", target["rawSql"]
    for ann in dashboard.get("annotations", {}).get("list", []):
        sql = ann.get("target", {}).get("rawSql")
        if sql:
            yield f"annotation {ann.get('name')!r}", sql


def test_customer_set_is_non_empty():
    assert CUSTOMER_FACING, "no customer-facing dashboards found"


@pytest.mark.parametrize("filename", CUSTOMER_FACING)
def test_customer_dashboard_sql_is_org_scoped(filename):
    dashboard = _load(filename)
    offenders = []
    for where, sql in _sql_targets(dashboard):
        if any(f"{name}(" in sql for name in _DORA_NAMES):
            if "$org" not in sql:
                offenders.append(f"{where} (DORA call without $org)")
            continue
        if any(name in sql for name in _DORA_NAMES):
            offenders.append(f"{where} (reads a NULL-org dora_* view)")
            continue
        if any(t in sql for t in ORG_SCOPED_TABLES) and "org_id" not in sql:
            offenders.append(f"{where} (no org_id filter)")
    assert not offenders, f"{filename}: {offenders}"


@pytest.mark.parametrize("filename", CUSTOMER_FACING)
def test_customer_dashboard_has_hidden_org_var(filename):
    dashboard = _load(filename)
    org_var = next(
        (v for v in dashboard.get("templating", {}).get("list", []) if v["name"] == "org"), None
    )
    assert org_var is not None, f"{filename}: missing 'org' template variable"
    assert org_var.get("hide") == 2, f"{filename}: 'org' var must be hidden (hide=2)"


@pytest.mark.parametrize("filename", CUSTOMER_FACING)
def test_customer_dashboard_sql_handles_multi_component_service(filename):
    # The proxy forwards a multi-component service as "a|b|c" (var-service).
    # A SQL panel matching `s.name = '$service'` would then match nothing.
    dashboard = _load(filename)
    offenders = [
        where
        for where, sql in _sql_targets(dashboard)
        if "$service" in sql and "s.name = '$service'" in sql
    ]
    assert not offenders, f"{filename}: bare s.name = '$service' breaks rolled-up services in {offenders}"


@pytest.mark.parametrize("filename", CUSTOMER_FACING)
def test_customer_dashboard_no_demo_hardcodes(filename):
    raw = (_CUSTOMER_DIR / filename).read_text()
    assert "sample-app" not in raw, f"{filename}: hardcoded demo workload reference"
