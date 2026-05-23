"""Integration tests: company filters tied to pipeline state, relationships, and export."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _stages(client: TestClient) -> dict[str, dict]:
    return {s["name"]: s for s in client.get("/pipeline-stages").json()}


def _create_company(client: TestClient, slug: str, owner_user_id: int = 1) -> int:
    r = client.post("/companies", json={
        "name": f"Filter Co {slug}",
        "industry_id": 1,
        "company_size": "startup",
        "country": "Polska",
        "city": "Krakow",
        "owner_user_id": owner_user_id,
    })
    assert r.status_code == 201
    return r.json()["id"]


def _create_event(client: TestClient, slug: str) -> int:
    r = client.post("/events", json={
        "name": f"Filter Event {slug}",
        "status": "active",
        "start_date": "2026-08-01",
        "owner_user_id": 1,
    })
    assert r.status_code == 201
    return r.json()["id"]


class TestCompanyPipelineFilters:
    """Company list filters by pipeline_stage_id and pipeline_outcome work correctly."""

    def test_filter_by_pipeline_outcome_won(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-fw")
        c_won = _create_company(client, f"{unique_slug}-won")
        c_open = _create_company(client, f"{unique_slug}-open")

        e1 = client.post("/pipeline-entries", json={"event_id": event_id, "company_id": c_won}).json()["id"]
        client.post("/pipeline-entries", json={"event_id": event_id, "company_id": c_open})

        client.post(f"/pipeline-entries/{e1}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 5000,
        })

        r = client.get(f"/companies?pipeline_outcome=won&event_id={event_id}")
        assert r.status_code == 200
        company_ids = [c["id"] for c in r.json()["items"]]
        assert c_won in company_ids
        assert c_open not in company_ids

    def test_filter_by_pipeline_outcome_lost(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-fl")
        c_lost = _create_company(client, f"{unique_slug}-lost")

        e1 = client.post("/pipeline-entries", json={"event_id": event_id, "company_id": c_lost}).json()["id"]
        client.post(f"/pipeline-entries/{e1}/move", json={
            "stage_id": stages["Odrzucony"]["id"], "rejection_reason": "Budget",
        })

        r = client.get(f"/companies?pipeline_outcome=lost&event_id={event_id}")
        assert r.status_code == 200
        company_ids = [c["id"] for c in r.json()["items"]]
        assert c_lost in company_ids

    def test_filter_by_pipeline_stage_id(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-fs")
        c1 = _create_company(client, f"{unique_slug}-s1")
        c2 = _create_company(client, f"{unique_slug}-s2")

        client.post("/pipeline-entries", json={"event_id": event_id, "company_id": c1})
        e2 = client.post("/pipeline-entries", json={"event_id": event_id, "company_id": c2}).json()["id"]
        client.post(f"/pipeline-entries/{e2}/move", json={
            "stage_id": stages["Oferta wysłana"]["id"],
        })

        offer_stage_id = stages["Oferta wysłana"]["id"]
        r = client.get(f"/companies?pipeline_stage_id={offer_stage_id}&event_id={event_id}")
        assert r.status_code == 200
        company_ids = [c["id"] for c in r.json()["items"]]
        assert c2 in company_ids
        assert c1 not in company_ids

    def test_filter_by_event_id(self, client: TestClient, unique_slug: str):
        event_id = _create_event(client, f"{unique_slug}-fe")
        c1 = _create_company(client, f"{unique_slug}-fec")

        client.post("/pipeline-entries", json={"event_id": event_id, "company_id": c1})

        r = client.get(f"/companies?event_id={event_id}")
        assert r.status_code == 200
        company_ids = [c["id"] for c in r.json()["items"]]
        assert c1 in company_ids


class TestCompanyRelationshipFilters:
    """Company filters by relation_status and relationship_type_id after pipeline WON + relationship activation."""

    def test_draft_relationship_not_in_active_filter(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-dra")
        company_id = _create_company(client, f"{unique_slug}-dra")

        e1 = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id,
        }).json()["id"]
        client.post(f"/pipeline-entries/{e1}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 5000,
        })

        r_active = client.get("/companies?relation_status=active")
        assert r_active.status_code == 200
        active_ids = [c["id"] for c in r_active.json()["items"]]
        assert company_id not in active_ids

    def test_active_relationship_in_active_filter(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-act")
        company_id = _create_company(client, f"{unique_slug}-act")

        e1 = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id,
        }).json()["id"]
        client.post(f"/pipeline-entries/{e1}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 8000,
        })

        rels = client.get(f"/company-relationships?company_id={company_id}").json()
        draft_rel = next((r for r in rels if r["status"] == "draft"), None)
        assert draft_rel is not None

        client.patch(f"/company-relationships/{draft_rel['id']}", json={"status": "active"})

        r_active = client.get("/companies?relation_status=active")
        assert r_active.status_code == 200
        active_ids = [c["id"] for c in r_active.json()["items"]]
        assert company_id in active_ids


class TestCompanyExportIntegration:
    """CSV export includes correct pipeline and partner data."""

    def test_export_csv_contains_won_company(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-exp")
        company_id = _create_company(client, f"{unique_slug}-exp")

        e1 = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id, "expected_amount": 20000,
        }).json()["id"]
        client.post(f"/pipeline-entries/{e1}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 20000,
        })

        r = client.get(f"/companies/export?event_id={event_id}")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert f"Filter Co {unique_slug}-exp" in r.text

    def test_export_csv_with_company_ids_filter(self, client: TestClient, unique_slug: str):
        c1 = _create_company(client, f"{unique_slug}-e1")
        c2 = _create_company(client, f"{unique_slug}-e2")
        c3 = _create_company(client, f"{unique_slug}-e3")

        r = client.get(f"/companies/export?company_ids={c1},{c2}")
        assert r.status_code == 200
        content = r.text
        assert f"Filter Co {unique_slug}-e1" in content
        assert f"Filter Co {unique_slug}-e2" in content
        assert f"Filter Co {unique_slug}-e3" not in content


class TestCompanyEventsAndActivitiesEndpoints:
    """Nested company endpoints reflect pipeline and activity state."""

    def test_company_events_shows_pipeline_link(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-ce")
        company_id = _create_company(client, f"{unique_slug}-ce")

        e1 = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id,
        }).json()["id"]
        client.post(f"/pipeline-entries/{e1}/move", json={
            "stage_id": stages["Oferta wysłana"]["id"],
        })

        r = client.get(f"/companies/{company_id}/events")
        assert r.status_code == 200
        data = r.json()
        event_ids = [e.get("event_id") or e.get("id") for e in data]
        assert event_id in event_ids

    def test_company_activities_shows_linked_activities(self, client: TestClient, unique_slug: str):
        company_id = _create_company(client, f"{unique_slug}-ca")

        client.post("/activities", json={
            "activity_type": "email",
            "subject": f"Email sent {unique_slug}",
            "company_id": company_id,
            "activity_date": "2026-05-15T10:00:00",
        })

        r = client.get(f"/companies/{company_id}/activities")
        assert r.status_code == 200
        subjects = [a.get("subject") for a in r.json()]
        assert f"Email sent {unique_slug}" in subjects
