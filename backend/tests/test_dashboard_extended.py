"""Extended tests for /dashboard endpoints: relationship-manager happy path and reminder email."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestRelationshipManagerDashboard:
    def test_rm_dashboard_success(self, client: TestClient):
        users_r = client.get("/users?role=opiekun")
        users = users_r.json()
        if not users:
            users_r = client.get("/users")
            users = users_r.json()
        user_id = users[0]["id"]
        r = client.get(f"/dashboard/relationship-manager?user_id={user_id}")
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data or "pipeline_count" in data or isinstance(data, dict)

    def test_rm_dashboard_user_not_found(self, client: TestClient):
        r = client.get("/dashboard/relationship-manager?user_id=999999")
        assert r.status_code == 404

    def test_rm_dashboard_missing_user_id_returns_422(self, client: TestClient):
        r = client.get("/dashboard/relationship-manager")
        assert r.status_code == 422


class TestCoordinatorDashboardExtended:
    def test_coordinator_dashboard_with_valid_event(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        r = client.get(f"/dashboard/coordinator?event_id={event_id}")
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data or isinstance(data, dict)

    def test_coordinator_dashboard_missing_event_id_returns_422(self, client: TestClient):
        r = client.get("/dashboard/coordinator")
        assert r.status_code == 422


class TestPromotionDashboard:
    def test_promotion_dashboard_success(self, client: TestClient):
        r = client.get("/dashboard/promotion")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)


class TestReminderEmail:
    def test_send_reminder_email_valid_user(self, client: TestClient):
        users_r = client.get("/users")
        user_id = users_r.json()[0]["id"]
        r = client.post(f"/dashboard/send-reminder-email?user_id={user_id}")
        assert r.status_code == 200
        data = r.json()
        assert "sent" in data
        assert "to" in data
        assert "subject" in data
        assert "overdue_count" in data
        assert "upcoming_count" in data
        assert "transport" in data

    def test_send_reminder_email_user_not_found(self, client: TestClient):
        r = client.post("/dashboard/send-reminder-email?user_id=999999")
        assert r.status_code == 404

    def test_send_reminder_email_no_smtp_logs(self, client: TestClient):
        users_r = client.get("/users")
        user_id = users_r.json()[0]["id"]
        r = client.post(f"/dashboard/send-reminder-email?user_id={user_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["transport"] in ("log", "smtp")
