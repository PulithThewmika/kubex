"""Guard: every SQL query in a customer-facing (embeddable) Grafana
dashboard must filter on org_id, so a future panel can't silently
reintroduce the cross-tenant leak fixed in #833.

The set here mirrors app.routers.grafana.EMBEDDABLE_DASHBOARD_UIDS. When
#834 splits the operator/customer dashboard sets, point this at that
folder instead.
"""

import json
from pathlib import Path

import pytest

_DASHBOARD_DIR = Path(__file__).resolve().parents[3] / "deploy" / "grafana" / "dashboards"
CUSTOMER_FACING = ["deploy-timeline.json"]

# Tables that carry org_id (CLAUDE.md decision 9). A query touching any of
# these must also constrain org_id.
ORG_SCOPED_TABLES = ("services", "deployments", "alerts", "pipeline_events")


def _sql_targets(dashboard: dict):
    for panel in dashboard.get("panels", []):
        for target in panel.get("targets", []):
            if target.get("rawSql"):
                yield f"panel {panel.get('id')}", target["rawSql"]
    for ann in dashboard.get("annotations", {}).get("list", []):
        sql = ann.get("target", {}).get("rawSql")
        if sql:
            yield f"annotation {ann.get('name')!r}", sql


@pytest.mark.parametrize("filename", CUSTOMER_FACING)
def test_customer_dashboard_sql_is_org_scoped(filename):
    dashboard = json.loads((_DASHBOARD_DIR / filename).read_text())
    offenders = []
    for where, sql in _sql_targets(dashboard):
        touches_org_table = any(t in sql for t in ORG_SCOPED_TABLES)
        if touches_org_table and "org_id" not in sql:
            offenders.append(where)
    assert not offenders, f"{filename}: unscoped SQL in {offenders}"


@pytest.mark.parametrize("filename", CUSTOMER_FACING)
def test_customer_dashboard_has_hidden_org_var(filename):
    dashboard = json.loads((_DASHBOARD_DIR / filename).read_text())
    org_var = next(
        (v for v in dashboard.get("templating", {}).get("list", []) if v["name"] == "org"),
        None,
    )
    assert org_var is not None, f"{filename}: missing 'org' template variable"
    assert org_var.get("hide") == 2, f"{filename}: 'org' var must be hidden (hide=2)"


@pytest.mark.parametrize("filename", CUSTOMER_FACING)
def test_customer_dashboard_sql_handles_multi_component_service(filename):
    # The proxy forwards a multi-component service as "a|b|c" (var-service).
    # A SQL panel matching `s.name = '$service'` would then match nothing —
    # it must split the alternation (string_to_array / ANY / regex).
    dashboard = json.loads((_DASHBOARD_DIR / filename).read_text())
    offenders = [
        where
        for where, sql in _sql_targets(dashboard)
        if "$service" in sql and "s.name = '$service'" in sql
    ]
    assert not offenders, f"{filename}: bare s.name = '$service' breaks rolled-up services in {offenders}"


@pytest.mark.parametrize("filename", CUSTOMER_FACING)
def test_customer_dashboard_no_demo_hardcodes(filename):
    raw = (_DASHBOARD_DIR / filename).read_text()
    assert "sample-app" not in raw, f"{filename}: hardcoded demo workload reference"
