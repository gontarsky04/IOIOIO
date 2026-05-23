"""Tests for /activities CRUD endpoints and filters."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


class TestActivitiesList:
    def test_list_activities(self, client: TestClient):
        r = client.get("/activities")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "activity_type" in data[0]
        assert "subject" in data[0]

    def test_list_activities_filter_by_company(self, client: TestClient):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        r = client.get(f"/activities?company_id={company_id}")
        assert r.status_code == 200
        for activity in r.json():
            assert activity["company_id"] == company_id

    def test_list_activities_filter_by_event(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        r = client.get(f"/activities?event_id={event_id}")
        assert r.status_code == 200
        for activity in r.json():
            assert activity["event_id"] == event_id

    def test_list_activities_filter_by_assigned_user(self, client: TestClient):
        users_r = client.get("/users")
        user_id = users_r.json()[0]["id"]
        r = client.get(f"/activities?assigned_user_id={user_id}")
        assert r.status_code == 200
        for activity in r.json():
            assert activity["assigned_user_id"] == user_id

    def test_list_activities_limit(self, client: TestClient):
        r = client.get("/activities?limit=5")
        assert r.status_code == 200
        assert len(r.json()) <= 5

    def test_list_activities_limit_too_large(self, client: TestClient):
        r = client.get("/activities?limit=600")
        assert r.status_code == 422

    def test_list_activities_limit_too_small(self, client: TestClient):
        r = client.get("/activities?limit=0")
        assert r.status_code == 422

    def test_list_activities_due_before_filter(self, client: TestClient):
        future = "2027-12-31T23:59:59"
        r = client.get(f"/activities?due_before={future}")
        assert r.status_code == 200

    def test_list_activities_overdue_only(self, client: TestClient):
        r = client.get("/activities?overdue_only=true&limit=5")
        assert r.status_code == 200
        for activity in r.json():
            assert activity["completed_at"] is None
            assert activity["due_date"] is not None


class TestActivitiesCreate:
    def test_create_activity_success(self, client: TestClient, unique_slug: str):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        payload = {
            "activity_type": "note",
            "subject": f"Test note {unique_slug}",
            "description": "Test description",
            "company_id": company_id,
            "activity_date": "2026-05-23T10:00:00",
        }
        r = client.post("/activities", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["activity_type"] == "note"
        assert data["subject"] == payload["subject"]
        assert data["company_id"] == company_id
        assert "id" in data

    def test_create_activity_task_with_due_date(self, client: TestClient, unique_slug: str):
        due = "2026-06-01T10:00:00"
        payload = {
            "activity_type": "task",
            "subject": f"Follow up {unique_slug}",
            "due_date": due,
        }
        r = client.post("/activities", json=payload)
        assert r.status_code == 201
        assert r.json()["activity_type"] == "task"
        assert r.json()["due_date"] is not None

    def test_create_activity_missing_subject_returns_422(self, client: TestClient):
        payload = {"activity_type": "note"}
        r = client.post("/activities", json=payload)
        assert r.status_code == 422

    def test_create_activity_empty_subject_returns_422(self, client: TestClient):
        payload = {"activity_type": "note", "subject": ""}
        r = client.post("/activities", json=payload)
        assert r.status_code == 422

    def test_create_activity_invalid_type_returns_422(self, client: TestClient):
        payload = {"activity_type": "invalid_type", "subject": "Test"}
        r = client.post("/activities", json=payload)
        assert r.status_code == 422

    def test_create_all_activity_types(self, client: TestClient, unique_slug: str):
        for activity_type in ["note", "meeting", "email", "phone_call", "task", "follow_up"]:
            payload = {
                "activity_type": activity_type,
                "subject": f"Test {activity_type} {unique_slug}",
            }
            r = client.post("/activities", json=payload)
            assert r.status_code == 201, f"Failed for type: {activity_type}"


class TestActivitiesGetById:
    def test_get_activity_success(self, client: TestClient):
        activities_r = client.get("/activities?limit=1")
        activity_id = activities_r.json()[0]["id"]
        r = client.get(f"/activities/{activity_id}")
        assert r.status_code == 200
        assert r.json()["id"] == activity_id

    def test_get_activity_not_found(self, client: TestClient):
        r = client.get("/activities/999999")
        assert r.status_code == 404


class TestActivitiesUpdate:
    def test_update_activity_subject(self, client: TestClient, unique_slug: str):
        create_r = client.post("/activities", json={
            "activity_type": "note",
            "subject": f"Original {unique_slug}",
        })
        activity_id = create_r.json()["id"]
        new_subject = f"Updated {unique_slug}"
        r = client.patch(f"/activities/{activity_id}", json={"subject": new_subject})
        assert r.status_code == 200
        assert r.json()["subject"] == new_subject

    def test_update_activity_mark_completed(self, client: TestClient, unique_slug: str):
        create_r = client.post("/activities", json={
            "activity_type": "task",
            "subject": f"To complete {unique_slug}",
        })
        activity_id = create_r.json()["id"]
        now = "2026-05-23T12:00:00"
        r = client.patch(f"/activities/{activity_id}", json={"completed_at": now})
        assert r.status_code == 200
        assert r.json()["completed_at"] is not None

    def test_update_activity_not_found(self, client: TestClient):
        r = client.patch("/activities/999999", json={"subject": "X"})
        assert r.status_code == 404


class TestActivitiesDelete:
    def test_delete_activity_success(self, client: TestClient, unique_slug: str):
        create_r = client.post("/activities", json={
            "activity_type": "note",
            "subject": f"To delete {unique_slug}",
        })
        activity_id = create_r.json()["id"]
        r = client.delete(f"/activities/{activity_id}")
        assert r.status_code == 204
        get_r = client.get(f"/activities/{activity_id}")
        assert get_r.status_code == 404

    def test_delete_activity_not_found(self, client: TestClient):
        r = client.delete("/activities/999999")
        assert r.status_code == 404
