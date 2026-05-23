"""Extended tests for pipeline entries: bulk create, PATCH, DELETE, and additional transitions."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _create_temp_company(client: TestClient, slug: str) -> int:
    r = client.post("/companies", json={
        "name": f"Pipeline Co {slug}",
        "industry_id": 1,
        "company_size": "startup",
        "country": "PL",
        "city": "Krakow",
    })
    return r.json()["id"]


def _create_temp_event(client: TestClient, slug: str) -> int:
    r = client.post("/events", json={
        "name": f"Pipeline Event {slug}",
        "status": "draft",
    })
    return r.json()["id"]


def _get_stage_by_name(client: TestClient, name: str) -> int:
    stages_r = client.get("/pipeline-stages")
    for s in stages_r.json():
        if s["name"] == name:
            return s["id"]
    raise ValueError(f"Stage {name} not found")


class TestPipelineBulkCreate:
    def test_bulk_create_success(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        c1 = _create_temp_company(client, f"{unique_slug}-A")
        c2 = _create_temp_company(client, f"{unique_slug}-B")
        payload = {
            "event_id": event_id,
            "company_ids": [c1, c2],
        }
        r = client.post("/pipeline-entries/bulk", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert len(data["created"]) == 2
        assert data["skipped_company_ids"] == []

    def test_bulk_create_skips_duplicates(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        c1 = _create_temp_company(client, f"{unique_slug}-C")
        client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": c1,
        })
        payload = {
            "event_id": event_id,
            "company_ids": [c1],
        }
        r = client.post("/pipeline-entries/bulk", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert len(data["created"]) == 0
        assert c1 in data["skipped_company_ids"]

    def test_bulk_create_skips_nonexistent_companies(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        payload = {
            "event_id": event_id,
            "company_ids": [999998, 999999],
        }
        r = client.post("/pipeline-entries/bulk", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert len(data["created"]) == 0
        assert 999998 in data["skipped_company_ids"]
        assert 999999 in data["skipped_company_ids"]

    def test_bulk_create_dedupes_company_ids(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        c1 = _create_temp_company(client, f"{unique_slug}-D")
        payload = {
            "event_id": event_id,
            "company_ids": [c1, c1, c1],
        }
        r = client.post("/pipeline-entries/bulk", json=payload)
        assert r.status_code == 201
        assert len(r.json()["created"]) == 1

    def test_bulk_create_event_not_found(self, client: TestClient):
        payload = {
            "event_id": 999999,
            "company_ids": [1],
        }
        r = client.post("/pipeline-entries/bulk", json=payload)
        assert r.status_code == 404

    def test_bulk_create_empty_company_ids_returns_422(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        payload = {
            "event_id": event_id,
            "company_ids": [],
        }
        r = client.post("/pipeline-entries/bulk", json=payload)
        assert r.status_code == 422


class TestPipelinePatch:
    def test_patch_expected_amount(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
            "expected_amount": 5000,
        })
        entry_id = create_r.json()["id"]
        r = client.patch(f"/pipeline-entries/{entry_id}", json={"expected_amount": 15000})
        assert r.status_code == 200
        assert float(r.json()["expected_amount"]) == 15000

    def test_patch_notes(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        r = client.patch(f"/pipeline-entries/{entry_id}", json={"notes": "Updated notes"})
        assert r.status_code == 200
        assert r.json()["notes"] == "Updated notes"

    def test_patch_stage_id_valid(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        stages_r = client.get("/pipeline-stages")
        second_stage_id = stages_r.json()[1]["id"]
        r = client.patch(f"/pipeline-entries/{entry_id}", json={"stage_id": second_stage_id})
        assert r.status_code == 200
        assert r.json()["stage"]["id"] == second_stage_id

    def test_patch_stage_id_not_found(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        r = client.patch(f"/pipeline-entries/{entry_id}", json={"stage_id": 999999})
        assert r.status_code == 404

    def test_patch_not_found(self, client: TestClient):
        r = client.patch("/pipeline-entries/999999", json={"notes": "X"})
        assert r.status_code == 404


class TestPipelineDelete:
    def test_delete_entry_success(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        r = client.delete(f"/pipeline-entries/{entry_id}")
        assert r.status_code == 204
        get_r = client.get(f"/pipeline-entries/{entry_id}")
        assert get_r.status_code == 404

    def test_delete_entry_not_found(self, client: TestClient):
        r = client.delete("/pipeline-entries/999999")
        assert r.status_code == 404


class TestPipelineTransitionsExtended:
    def test_move_to_zainteresowany_sets_first_contact_at(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        zainteresowany_id = _get_stage_by_name(client, "Zainteresowany")
        r = client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": zainteresowany_id,
        })
        assert r.status_code == 200
        assert r.json()["first_contact_at"] is not None

    def test_move_to_lost_stores_rejection_reason(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        lost_id = _get_stage_by_name(client, "Odrzucony")
        r = client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": lost_id,
            "rejection_reason": "Budget too low",
        })
        assert r.status_code == 200
        assert r.json()["rejection_reason"] == "Budget too low"
        assert r.json()["closed_at"] is not None

    def test_move_from_lost_back_to_open_clears_rejection(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        lost_id = _get_stage_by_name(client, "Odrzucony")
        client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": lost_id,
            "rejection_reason": "Not interested",
        })
        kontakt_id = _get_stage_by_name(client, "Kontakt")
        r = client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": kontakt_id,
        })
        assert r.status_code == 200
        assert r.json()["rejection_reason"] is None
        assert r.json()["closed_at"] is None

    def test_move_to_won_with_agreed_amount(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        won_id = _get_stage_by_name(client, "Decyzja: TAK")
        r = client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": won_id,
            "agreed_amount": 25000,
        })
        assert r.status_code == 200
        assert float(r.json()["agreed_amount"]) == 25000
        assert r.json()["closed_at"] is not None

        rels_r = client.get(f"/company-relationships?company_id={company_id}")
        draft_rels = [rel for rel in rels_r.json() if rel["status"] == "draft"]
        assert len(draft_rels) >= 1

    def test_move_nonexistent_stage_returns_404(self, client: TestClient, unique_slug: str):
        event_id = _create_temp_event(client, unique_slug)
        company_id = _create_temp_company(client, unique_slug)
        create_r = client.post("/pipeline-entries", json={
            "event_id": event_id,
            "company_id": company_id,
        })
        entry_id = create_r.json()["id"]
        r = client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": 999999,
        })
        assert r.status_code == 404
