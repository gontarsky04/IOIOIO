"""Tests for /events CRUD endpoints (create, update, delete, get, reports)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestEventsCreate:
    def test_create_event_success(self, client: TestClient, unique_slug: str):
        payload = {
            "name": f"Test Event {unique_slug}",
            "description": "Test event description",
            "start_date": "2026-09-01",
            "end_date": "2026-09-02",
            "status": "draft",
            "target_budget": 50000,
            "target_partners_count": 10,
        }
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == payload["name"]
        assert data["status"] == "draft"
        assert float(data["target_budget"]) == 50000
        assert data["target_partners_count"] == 10
        assert "id" in data

    def test_create_event_with_tags(self, client: TestClient, unique_slug: str):
        tags_r = client.get("/tags")
        tag_ids = [t["id"] for t in tags_r.json()[:2]]
        payload = {
            "name": f"Tagged Event {unique_slug}",
            "status": "draft",
            "tag_ids": tag_ids,
        }
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        data = r.json()
        result_tag_ids = [t["id"] for t in data.get("tags", [])]
        for tid in tag_ids:
            assert tid in result_tag_ids

    def test_create_event_with_owner(self, client: TestClient, unique_slug: str):
        users_r = client.get("/users")
        user_id = users_r.json()[0]["id"]
        payload = {
            "name": f"Owned Event {unique_slug}",
            "status": "draft",
            "owner_user_id": user_id,
        }
        r = client.post("/events", json=payload)
        assert r.status_code == 201
        assert r.json()["owner_user_id"] == user_id

    def test_create_event_missing_name_returns_422(self, client: TestClient):
        payload = {"status": "draft"}
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_invalid_status_returns_422(self, client: TestClient):
        payload = {"name": "Bad Status", "status": "nonexistent"}
        r = client.post("/events", json=payload)
        assert r.status_code == 422

    def test_create_event_negative_budget_returns_422(self, client: TestClient):
        payload = {
            "name": "Negative Budget",
            "status": "draft",
            "target_budget": -100,
        }
        r = client.post("/events", json=payload)
        assert r.status_code == 422


class TestEventsUpdate:
    def test_update_event_name(self, client: TestClient, unique_slug: str):
        create_r = client.post("/events", json={
            "name": f"To Update {unique_slug}",
            "status": "draft",
        })
        event_id = create_r.json()["id"]
        new_name = f"Updated {unique_slug}"
        r = client.patch(f"/events/{event_id}", json={"name": new_name})
        assert r.status_code == 200
        assert r.json()["name"] == new_name

    def test_update_event_status(self, client: TestClient, unique_slug: str):
        create_r = client.post("/events", json={
            "name": f"Status Change {unique_slug}",
            "status": "draft",
        })
        event_id = create_r.json()["id"]
        r = client.patch(f"/events/{event_id}", json={"status": "active"})
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    def test_update_event_tags_replace(self, client: TestClient, unique_slug: str):
        tags_r = client.get("/tags")
        all_tags = tags_r.json()
        create_r = client.post("/events", json={
            "name": f"Tag Replace {unique_slug}",
            "status": "draft",
            "tag_ids": [all_tags[0]["id"]],
        })
        event_id = create_r.json()["id"]
        new_tag_ids = [all_tags[1]["id"], all_tags[2]["id"]]
        r = client.patch(f"/events/{event_id}", json={"tag_ids": new_tag_ids})
        assert r.status_code == 200
        result_tag_ids = [t["id"] for t in r.json()["tags"]]
        assert set(result_tag_ids) == set(new_tag_ids)

    def test_update_event_not_found(self, client: TestClient):
        r = client.patch("/events/999999", json={"name": "X"})
        assert r.status_code == 404


class TestEventsDelete:
    def test_delete_event_success(self, client: TestClient, unique_slug: str):
        create_r = client.post("/events", json={
            "name": f"To Delete {unique_slug}",
            "status": "draft",
        })
        event_id = create_r.json()["id"]
        r = client.delete(f"/events/{event_id}")
        assert r.status_code == 204
        get_r = client.get(f"/events/{event_id}")
        assert get_r.status_code == 404

    def test_delete_event_not_found(self, client: TestClient):
        r = client.delete("/events/999999")
        assert r.status_code == 404


class TestEventsGetById:
    def test_get_event_success(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        r = client.get(f"/events/{event_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == event_id
        assert "name" in data
        assert "status" in data

    def test_get_event_not_found(self, client: TestClient):
        r = client.get("/events/999999")
        assert r.status_code == 404


class TestEventReport:
    def test_event_report_success(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        r = client.get(f"/events/{event_id}/report")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_event_report_not_found(self, client: TestClient):
        r = client.get("/events/999999/report")
        assert r.status_code == 404


class TestEventCompanyReport:
    def test_event_company_report_success(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        pipeline_r = client.get(f"/events/{event_id}/pipeline")
        if pipeline_r.json():
            company_id = pipeline_r.json()[0]["company"]["id"]
            r = client.get(f"/events/{event_id}/companies/{company_id}/report")
            assert r.status_code == 200
            data = r.json()
            assert data["event_id"] == event_id
            assert data["company_id"] == company_id
            assert "pipeline_entry" in data
            assert "activities" in data

    def test_event_company_report_event_not_found(self, client: TestClient):
        r = client.get("/events/999999/companies/1/report")
        assert r.status_code == 404

    def test_event_company_report_company_not_found(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        r = client.get(f"/events/{event_id}/companies/999999/report")
        assert r.status_code == 404
