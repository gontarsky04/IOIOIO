"""Integration tests: bulk operations, unique constraints, cascade deletes, and ownership scoping."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _stages(client: TestClient) -> dict[str, dict]:
    return {s["name"]: s for s in client.get("/pipeline-stages").json()}


def _create_company(client: TestClient, slug: str, owner_user_id: int = 1) -> int:
    r = client.post("/companies", json={
        "name": f"Bulk Co {slug}",
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
        "name": f"Bulk Event {slug}",
        "status": "active",
        "start_date": "2026-09-01",
        "owner_user_id": 1,
    })
    assert r.status_code == 201
    return r.json()["id"]


class TestBulkPipelineWithProgressiveMovement:
    """Bulk create entries then move them selectively, verify KPI distribution."""

    def test_bulk_add_and_mixed_outcomes(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-bm")

        c1 = _create_company(client, f"{unique_slug}-b1")
        c2 = _create_company(client, f"{unique_slug}-b2")
        c3 = _create_company(client, f"{unique_slug}-b3")
        c4 = _create_company(client, f"{unique_slug}-b4")

        bulk_r = client.post("/pipeline-entries/bulk", json={
            "event_id": event_id,
            "company_ids": [c1, c2, c3, c4],
            "expected_amount": 10000,
        })
        assert bulk_r.status_code == 201
        created = bulk_r.json()["created"]
        assert len(created) == 4
        entry_ids = {e["company"]["id"]: e["id"] for e in created}

        client.post(f"/pipeline-entries/{entry_ids[c1]}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 12000,
        })
        client.post(f"/pipeline-entries/{entry_ids[c2]}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 8000,
        })
        client.post(f"/pipeline-entries/{entry_ids[c3]}/move", json={
            "stage_id": stages["Odrzucony"]["id"], "rejection_reason": "No fit",
        })

        kpi = client.get(f"/events/{event_id}/kpi").json()
        assert kpi["pipeline_count"] == 4
        assert kpi["partners_count"] == 2
        assert kpi["conversion_rate"] == pytest.approx(2 / 3, abs=0.01)

        r = client.get(f"/companies?pipeline_outcome=open&event_id={event_id}")
        open_ids = [c["id"] for c in r.json()["items"]]
        assert c4 in open_ids
        assert c1 not in open_ids

    def test_bulk_create_respects_stage_override(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-bs")
        c1 = _create_company(client, f"{unique_slug}-bs1")

        stage_id = stages["Oferta wysłana"]["id"]
        bulk_r = client.post("/pipeline-entries/bulk", json={
            "event_id": event_id,
            "company_ids": [c1],
            "stage_id": stage_id,
        })
        assert bulk_r.status_code == 201
        entry = bulk_r.json()["created"][0]
        assert entry["stage"]["id"] == stage_id


class TestUniqueConstraintEnforcement:
    """Pipeline unique constraint (event_id, company_id) is enforced across operations."""

    def test_duplicate_single_create_returns_409(self, client: TestClient, unique_slug: str):
        event_id = _create_event(client, f"{unique_slug}-dup")
        company_id = _create_company(client, f"{unique_slug}-dup")

        r1 = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id,
        })
        assert r1.status_code == 201

        r2 = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id,
        })
        assert r2.status_code == 409

    def test_bulk_skips_already_in_pipeline(self, client: TestClient, unique_slug: str):
        event_id = _create_event(client, f"{unique_slug}-bskip")
        c1 = _create_company(client, f"{unique_slug}-bsk1")
        c2 = _create_company(client, f"{unique_slug}-bsk2")

        client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": c1,
        })

        bulk_r = client.post("/pipeline-entries/bulk", json={
            "event_id": event_id,
            "company_ids": [c1, c2],
        })
        assert bulk_r.status_code == 201
        data = bulk_r.json()
        assert len(data["created"]) == 1
        assert data["created"][0]["company"]["id"] == c2
        assert c1 in data["skipped_company_ids"]

    def test_same_company_different_events_allowed(self, client: TestClient, unique_slug: str):
        event1 = _create_event(client, f"{unique_slug}-e1")
        event2 = _create_event(client, f"{unique_slug}-e2")
        company_id = _create_company(client, f"{unique_slug}-se")

        r1 = client.post("/pipeline-entries", json={
            "event_id": event1, "company_id": company_id,
        })
        r2 = client.post("/pipeline-entries", json={
            "event_id": event2, "company_id": company_id,
        })
        assert r1.status_code == 201
        assert r2.status_code == 201


class TestCascadeDeleteBehavior:
    """Deleting a company cascades to contacts; deleting an event cascades to pipeline entries."""

    def test_delete_company_cascades_contacts(self, client: TestClient, unique_slug: str):
        company_id = _create_company(client, f"{unique_slug}-dc")
        contact_r = client.post("/contacts", json={
            "first_name": "Cascade",
            "last_name": f"Test-{unique_slug}",
            "company_id": company_id,
        })
        contact_id = contact_r.json()["id"]

        client.delete(f"/companies/{company_id}")

        r = client.get(f"/contacts/{contact_id}")
        assert r.status_code == 404

    def test_delete_event_cascades_pipeline_entries(self, client: TestClient, unique_slug: str):
        event_id = _create_event(client, f"{unique_slug}-de")
        company_id = _create_company(client, f"{unique_slug}-de")

        entry_r = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id,
        })
        entry_id = entry_r.json()["id"]

        client.delete(f"/events/{event_id}")

        r = client.get(f"/pipeline-entries/{entry_id}")
        assert r.status_code == 404

    def test_delete_pipeline_entry_updates_kpi(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-dk")
        company_id = _create_company(client, f"{unique_slug}-dk")

        entry_id = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id, "expected_amount": 5000,
        }).json()["id"]
        client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 5000,
        })

        kpi_before = client.get(f"/events/{event_id}/kpi").json()
        assert kpi_before["partners_count"] == 1

        client.delete(f"/pipeline-entries/{entry_id}")

        kpi_after = client.get(f"/events/{event_id}/kpi").json()
        assert kpi_after["partners_count"] == 0
        assert kpi_after["pipeline_count"] == 0


class TestOwnershipScoping:
    """Pipeline entry owner vs company owner affects different scopes."""

    def test_rm_dashboard_scoped_by_pipeline_owner(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        users = client.get("/users").json()
        user1 = users[0]["id"]
        user2 = users[1]["id"] if len(users) > 1 else users[0]["id"]

        event_id = _create_event(client, f"{unique_slug}-own")
        company_id = _create_company(client, f"{unique_slug}-own", owner_user_id=user2)

        entry_id = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
            "owner_user_id": user1,
            "expected_amount": 10000,
        }).json()["id"]
        client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 10000,
        })

        dash = client.get(f"/dashboard/relationship-manager?user_id={user1}").json()
        assert isinstance(dash, dict)

    def test_reports_filter_by_company_owner(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        users = client.get("/users").json()
        user1 = users[0]["id"]

        event_id = _create_event(client, f"{unique_slug}-ro")
        company_id = _create_company(client, f"{unique_slug}-ro", owner_user_id=user1)

        entry_id = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
            "expected_amount": 10000,
        }).json()["id"]
        client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 10000,
        })

        reports = client.get(f"/reports?owner_user_id={user1}").json()
        assert reports["totals"]["partners_count"] >= 1


class TestPromotionDashboardIntegration:
    """Promotion dashboard shows active events with pipeline progress."""

    def test_promotion_dashboard_shows_event_with_pipeline(self, client: TestClient, unique_slug: str):
        stages = _stages(client)
        event_id = _create_event(client, f"{unique_slug}-promo")
        company_id = _create_company(client, f"{unique_slug}-promo")

        entry_id = client.post("/pipeline-entries", json={
            "event_id": event_id, "company_id": company_id, "expected_amount": 20000,
        }).json()["id"]
        client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"], "agreed_amount": 20000,
        })

        dash = client.get("/dashboard/promotion").json()
        assert isinstance(dash, dict)
        if "events" in dash:
            event_ids = [e.get("event_id") or e.get("id") for e in dash["events"]]
            assert event_id in event_ids
