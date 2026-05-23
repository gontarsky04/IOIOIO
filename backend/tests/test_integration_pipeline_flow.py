"""Integration tests: full pipeline lifecycle (Kontakt → WON/LOST) with KPI, dashboard, reports verification."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _stages(client: TestClient) -> dict[str, dict]:
    return {s["name"]: s for s in client.get("/pipeline-stages").json()}


def _create_company(client: TestClient, slug: str) -> int:
    r = client.post("/companies", json={
        "name": f"Integration Co {slug}",
        "industry_id": 1,
        "company_size": "startup",
        "country": "Polska",
        "city": "Krakow",
        "owner_user_id": 1,
    })
    assert r.status_code == 201
    return r.json()["id"]


def _create_event(client: TestClient, slug: str, target_budget=100000, target_partners=5) -> int:
    r = client.post("/events", json={
        "name": f"Integration Event {slug}",
        "status": "active",
        "start_date": "2026-06-01",
        "end_date": "2026-06-03",
        "target_budget": target_budget,
        "target_partners_count": target_partners,
        "owner_user_id": 1,
    })
    assert r.status_code == 201
    return r.json()["id"]


def _create_entry(client: TestClient, event_id: int, company_id: int, expected_amount=None, owner_user_id=None) -> int:
    payload: dict = {"event_id": event_id, "company_id": company_id}
    if expected_amount is not None:
        payload["expected_amount"] = expected_amount
    if owner_user_id is not None:
        payload["owner_user_id"] = owner_user_id
    r = client.post("/pipeline-entries", json=payload)
    assert r.status_code == 201
    return r.json()["id"]


def _move(client: TestClient, entry_id: int, stage_id: int, **kwargs) -> dict:
    payload = {"stage_id": stage_id, **kwargs}
    r = client.post(f"/pipeline-entries/{entry_id}/move", json=payload)
    assert r.status_code == 200
    return r.json()


class TestHappyPathKontaktToWon:
    """Full pipeline journey from Kontakt through all stages to WON, verifying KPI, dashboard, reports."""

    def test_full_pipeline_lifecycle(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        company_id = _create_company(client, unique_slug)
        event_id = _create_event(client, unique_slug, target_budget=50000, target_partners=2)

        entry_id = _create_entry(client, event_id, company_id, expected_amount=20000, owner_user_id=1)

        kpi_before = client.get(f"/events/{event_id}/kpi").json()
        assert kpi_before["pipeline_count"] == 1
        assert kpi_before["partners_count"] == 0

        entry = _move(client, entry_id, stages["Zainteresowany"]["id"])
        assert entry["first_contact_at"] is not None
        first_contact_at = entry["first_contact_at"]

        entry = _move(client, entry_id, stages["Oferta wysłana"]["id"])
        assert entry["offer_sent_at"] is not None
        assert entry["first_contact_at"] == first_contact_at

        entry = _move(client, entry_id, stages["Negocjacje"]["id"])
        assert entry["offer_sent_at"] is not None

        entry = _move(client, entry_id, stages["Decyzja: TAK"]["id"], agreed_amount=25000)
        assert entry["closed_at"] is not None
        assert float(entry["agreed_amount"]) == 25000

        kpi_after = client.get(f"/events/{event_id}/kpi").json()
        assert kpi_after["partners_count"] == 1
        assert kpi_after["pipeline_count"] == 1
        assert kpi_after["conversion_rate"] == 1.0

        rels_r = client.get(f"/company-relationships?company_id={company_id}&event_id={event_id}")
        assert rels_r.status_code == 200
        draft_rels = [r for r in rels_r.json() if r["status"] == "draft"]
        assert len(draft_rels) >= 1
        assert draft_rels[0]["pipeline_entry_id"] == entry_id
        assert float(draft_rels[0]["amount_net"]) == 25000

        company_r = client.get(f"/companies/{company_id}")
        assert company_r.json()["is_partner"] is True

        pipeline_r = client.get(f"/events/{event_id}/pipeline")
        won_entries = [e for e in pipeline_r.json() if e["stage"]["name"] == "Decyzja: TAK"]
        assert len(won_entries) == 1
        assert won_entries[0]["company"]["id"] == company_id

    def test_kpi_progress_caps_at_one(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-cap", target_budget=1000, target_partners=1)

        c1 = _create_company(client, f"{unique_slug}-cap1")
        c2 = _create_company(client, f"{unique_slug}-cap2")
        e1 = _create_entry(client, event_id, c1, expected_amount=5000)
        e2 = _create_entry(client, event_id, c2, expected_amount=5000)

        _move(client, e1, stages["Decyzja: TAK"]["id"], agreed_amount=5000)
        _move(client, e2, stages["Decyzja: TAK"]["id"], agreed_amount=5000)

        kpi = client.get(f"/events/{event_id}/kpi").json()
        assert kpi["partners_count"] == 2
        assert kpi["progress_partners_pct"] <= 1.0
        assert kpi["progress_budget_pct"] <= 1.0

    def test_conversion_rate_excludes_open(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-conv")

        c1 = _create_company(client, f"{unique_slug}-won")
        c2 = _create_company(client, f"{unique_slug}-lost")
        c3 = _create_company(client, f"{unique_slug}-open")
        e1 = _create_entry(client, event_id, c1, expected_amount=10000)
        e2 = _create_entry(client, event_id, c2, expected_amount=10000)
        _create_entry(client, event_id, c3, expected_amount=10000)

        _move(client, e1, stages["Decyzja: TAK"]["id"], agreed_amount=10000)
        _move(client, e2, stages["Odrzucony"]["id"], rejection_reason="No budget")

        kpi = client.get(f"/events/{event_id}/kpi").json()
        assert kpi["pipeline_count"] == 3
        assert kpi["partners_count"] == 1
        assert kpi["conversion_rate"] == pytest.approx(0.5, abs=0.01)


class TestLostPathAndRevert:
    """Test LOST flow with rejection and revert back to open."""

    def test_lost_then_revert_to_open(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-rev")
        company_id = _create_company(client, f"{unique_slug}-rev")
        entry_id = _create_entry(client, event_id, company_id, expected_amount=15000)

        _move(client, entry_id, stages["Zainteresowany"]["id"])
        entry = _move(client, entry_id, stages["Odrzucony"]["id"], rejection_reason="Too expensive")
        assert entry["rejection_reason"] == "Too expensive"
        assert entry["closed_at"] is not None

        kpi = client.get(f"/events/{event_id}/kpi").json()
        assert kpi["partners_count"] == 0
        assert kpi["conversion_rate"] is None or kpi["conversion_rate"] == 0.0

        entry = _move(client, entry_id, stages["Negocjacje"]["id"])
        assert entry["rejection_reason"] is None
        assert entry["closed_at"] is None

        kpi = client.get(f"/events/{event_id}/kpi").json()
        assert kpi["conversion_rate"] is None or kpi["conversion_rate"] == 0.0


class TestPatchBypassesBusinessRules:
    """Verify that PATCH /pipeline-entries/{id} does NOT trigger transition side effects."""

    def test_patch_stage_does_not_set_timestamps(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-patch")
        company_id = _create_company(client, f"{unique_slug}-patch")
        entry_id = _create_entry(client, event_id, company_id)

        won_stage_id = stages["Decyzja: TAK"]["id"]
        r = client.patch(f"/pipeline-entries/{entry_id}", json={"stage_id": won_stage_id})
        assert r.status_code == 200
        data = r.json()
        assert data["first_contact_at"] is None
        assert data["offer_sent_at"] is None
        assert data["closed_at"] is None

        rels_r = client.get(f"/company-relationships?company_id={company_id}&event_id={event_id}")
        draft_rels = [rel for rel in rels_r.json() if rel.get("pipeline_entry_id") == entry_id]
        assert len(draft_rels) == 0


class TestCoordinatorDashboardIntegration:
    """Coordinator dashboard reflects pipeline and activity state."""

    def test_dashboard_reflects_pipeline_won(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-dash", target_budget=50000, target_partners=3)
        company_id = _create_company(client, f"{unique_slug}-dash")
        entry_id = _create_entry(client, event_id, company_id, expected_amount=20000, owner_user_id=1)

        dash_before = client.get(f"/dashboard/coordinator?event_id={event_id}").json()

        _move(client, entry_id, stages["Decyzja: TAK"]["id"], agreed_amount=20000)

        dash_after = client.get(f"/dashboard/coordinator?event_id={event_id}").json()
        assert dash_after["kpi_partners_count"] > dash_before["kpi_partners_count"]

    def test_dashboard_shows_activities(self, client: TestClient, unique_slug: str):
        event_id = _create_event(client, f"{unique_slug}-dact")
        company_id = _create_company(client, f"{unique_slug}-dact")

        client.post("/activities", json={
            "activity_type": "task",
            "subject": f"Dashboard task {unique_slug}",
            "event_id": event_id,
            "company_id": company_id,
            "due_date": "2026-06-10T10:00:00",
            "assigned_user_id": 1,
        })

        dash = client.get(f"/dashboard/coordinator?event_id={event_id}").json()
        assert "upcoming_tasks" in dash or "recent_activities" in dash


class TestReportsIntegration:
    """Reports aggregate pipeline data across events correctly."""

    def test_reports_include_won_entry(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-rep")
        company_id = _create_company(client, f"{unique_slug}-rep")
        entry_id = _create_entry(client, event_id, company_id, expected_amount=30000)

        _move(client, entry_id, stages["Decyzja: TAK"]["id"], agreed_amount=35000)

        reports = client.get(f"/reports?event_id={event_id}").json()
        assert reports["totals"]["partners_count"] >= 1
        assert float(reports["totals"]["total_value"]) > 0

        assert len(reports["events"]) >= 1
        event_report = next((e for e in reports["events"] if e["event_id"] == event_id), None)
        assert event_report is not None
        assert event_report["partners_count"] >= 1

    def test_reports_pipeline_stages_distribution(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-dist")

        c1 = _create_company(client, f"{unique_slug}-d1")
        c2 = _create_company(client, f"{unique_slug}-d2")
        c3 = _create_company(client, f"{unique_slug}-d3")
        _create_entry(client, event_id, c1)
        e2 = _create_entry(client, event_id, c2, expected_amount=10000)
        e3 = _create_entry(client, event_id, c3, expected_amount=20000)
        _move(client, e2, stages["Oferta wysłana"]["id"])
        _move(client, e3, stages["Decyzja: TAK"]["id"], agreed_amount=20000)

        reports = client.get(f"/reports?event_id={event_id}").json()
        stage_names = [s["stage_name"] for s in reports["pipeline_stages"]]
        assert "Kontakt" in stage_names
        assert "Decyzja: TAK" in stage_names

    def test_event_report_endpoint(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-er")
        company_id = _create_company(client, f"{unique_slug}-er")
        entry_id = _create_entry(client, event_id, company_id, expected_amount=15000)
        _move(client, entry_id, stages["Decyzja: TAK"]["id"], agreed_amount=15000)

        r = client.get(f"/events/{event_id}/report")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_csv_export_includes_event_data(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-csv")
        company_id = _create_company(client, f"{unique_slug}-csv")
        entry_id = _create_entry(client, event_id, company_id, expected_amount=10000)
        _move(client, entry_id, stages["Decyzja: TAK"]["id"], agreed_amount=10000)

        r = client.get(f"/reports/export.csv?event_id={event_id}")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert f"Integration Event {unique_slug}-csv" in r.text
