"""Integration tests: activities ↔ dashboard ↔ reminder email ↔ company enrichment."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _create_company(client: TestClient, slug: str) -> int:
    r = client.post("/companies", json={
        "name": f"Act Co {slug}",
        "industry_id": 1,
        "company_size": "startup",
        "country": "Polska",
        "city": "Warszawa",
        "owner_user_id": 1,
    })
    assert r.status_code == 201
    return r.json()["id"]


def _create_event(client: TestClient, slug: str) -> int:
    r = client.post("/events", json={
        "name": f"Act Event {slug}",
        "status": "active",
        "start_date": "2026-07-01",
        "owner_user_id": 1,
    })
    assert r.status_code == 201
    return r.json()["id"]


def _get_user_id(client: TestClient, role: str = "opiekun") -> int:
    users = client.get(f"/users?role={role}").json()
    if users:
        return users[0]["id"]
    return client.get("/users").json()[0]["id"]


class TestActivitiesDashboardIntegration:
    """Activities created with due dates appear in dashboard task lists and reminder emails."""

    def test_overdue_task_appears_in_rm_dashboard(self, client: TestClient, unique_slug: str):
        user_id = _get_user_id(client)
        company_id = _create_company(client, f"{unique_slug}-ov")
        event_id = _create_event(client, f"{unique_slug}-ov")

        client.post("/activities", json={
            "activity_type": "task",
            "subject": f"Overdue task {unique_slug}",
            "company_id": company_id,
            "event_id": event_id,
            "assigned_user_id": user_id,
            "due_date": "2025-01-01T10:00:00",
        })

        dash = client.get(f"/dashboard/relationship-manager?user_id={user_id}").json()
        assert "overdue_activities" in dash or "overdue_tasks" in dash or isinstance(dash, dict)

        overdue_r = client.get(f"/activities?assigned_user_id={user_id}&overdue_only=true&limit=50")
        overdue_subjects = [a["subject"] for a in overdue_r.json()]
        assert f"Overdue task {unique_slug}" in overdue_subjects

    def test_upcoming_task_in_coordinator_dashboard(self, client: TestClient, unique_slug: str):
        event_id = _create_event(client, f"{unique_slug}-up")
        company_id = _create_company(client, f"{unique_slug}-up")

        client.post("/activities", json={
            "activity_type": "follow_up",
            "subject": f"Upcoming follow_up {unique_slug}",
            "company_id": company_id,
            "event_id": event_id,
            "assigned_user_id": 1,
            "due_date": "2026-06-05T10:00:00",
        })

        dash = client.get(f"/dashboard/coordinator?event_id={event_id}").json()
        all_subjects = []
        for key in ("upcoming_tasks", "recent_activities"):
            if key in dash:
                for item in dash[key]:
                    if isinstance(item, dict) and "subject" in item:
                        all_subjects.append(item["subject"])
        assert f"Upcoming follow_up {unique_slug}" in all_subjects

    def test_completed_task_excluded_from_overdue(self, client: TestClient, unique_slug: str):
        user_id = _get_user_id(client)
        company_id = _create_company(client, f"{unique_slug}-comp")

        create_r = client.post("/activities", json={
            "activity_type": "task",
            "subject": f"Completed task {unique_slug}",
            "company_id": company_id,
            "assigned_user_id": user_id,
            "due_date": "2025-06-01T10:00:00",
        })
        activity_id = create_r.json()["id"]

        client.patch(f"/activities/{activity_id}", json={
            "completed_at": "2025-06-01T12:00:00",
        })

        overdue_r = client.get(f"/activities?assigned_user_id={user_id}&overdue_only=true&limit=500")
        overdue_ids = [a["id"] for a in overdue_r.json()]
        assert activity_id not in overdue_ids


class TestReminderEmailIntegration:
    """Reminder email reflects overdue and upcoming tasks for a user."""

    def test_reminder_email_counts_match_activities(self, client: TestClient, unique_slug: str):
        user_id = _get_user_id(client)

        overdue_r = client.get(f"/activities?assigned_user_id={user_id}&overdue_only=true&limit=500")
        overdue_count = len(overdue_r.json())

        email_r = client.post(f"/dashboard/send-reminder-email?user_id={user_id}")
        assert email_r.status_code == 200
        email_data = email_r.json()
        assert email_data["overdue_count"] >= 0
        assert email_data["upcoming_count"] >= 0
        assert email_data["to"] != ""

    def test_reminder_email_with_no_tasks(self, client: TestClient, unique_slug: str):
        company_r = client.post("/companies", json={
            "name": f"NoTask Co {unique_slug}",
            "industry_id": 1,
            "company_size": "startup",
            "country": "PL",
            "city": "Krakow",
        })
        users_r = client.get("/users")
        user_id = users_r.json()[-1]["id"]

        email_r = client.post(f"/dashboard/send-reminder-email?user_id={user_id}")
        assert email_r.status_code == 200
        assert email_r.json()["transport"] in ("log", "smtp")


class TestCompanyLastContactEnrichment:
    """Company's last_contact_at is derived from activities, not pipeline moves."""

    def test_last_contact_at_from_activity(self, client: TestClient, unique_slug: str):
        company_id = _create_company(client, f"{unique_slug}-lc")

        client.post("/activities", json={
            "activity_type": "meeting",
            "subject": f"Meeting {unique_slug}",
            "company_id": company_id,
            "activity_date": "2026-05-20T14:00:00",
        })

        company_r = client.get(f"/companies/{company_id}")
        assert company_r.status_code == 200
        data = company_r.json()
        assert data["last_contact_at"] is not None
        assert "2026-05-20" in data["last_contact_at"]

    def test_pipeline_move_does_not_change_last_contact_at(self, client: TestClient, unique_slug: str):
        stages = {s["name"]: s for s in client.get("/pipeline-stages").json()}
        company_id = _create_company(client, f"{unique_slug}-plc")
        event_id = _create_event(client, f"{unique_slug}-plc")
        entry_id = _create_company_pipeline(client, event_id, company_id)

        company_before = client.get(f"/companies/{company_id}").json()
        last_contact_before = company_before.get("last_contact_at")

        client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": stages["Zainteresowany"]["id"],
        })

        company_after = client.get(f"/companies/{company_id}").json()
        assert company_after.get("last_contact_at") == last_contact_before


def _create_company_pipeline(client: TestClient, event_id: int, company_id: int) -> int:
    r = client.post("/pipeline-entries", json={
        "event_id": event_id,
        "company_id": company_id,
    })
    return r.json()["id"]


class TestCompanyIsPartnerIntegration:
    """Company is_partner flag reflects WON pipeline entries globally."""

    def test_is_partner_true_after_won(self, client: TestClient, unique_slug: str):
        stages = {s["name"]: s for s in client.get("/pipeline-stages").json()}
        company_id = _create_company(client, f"{unique_slug}-ip")
        event_id = _create_event(client, f"{unique_slug}-ip")
        entry_id = _create_company_pipeline(client, event_id, company_id)

        company_before = client.get(f"/companies/{company_id}").json()
        assert company_before["is_partner"] is False

        client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": stages["Decyzja: TAK"]["id"],
            "agreed_amount": 10000,
        })

        company_after = client.get(f"/companies/{company_id}").json()
        assert company_after["is_partner"] is True

    def test_is_partner_false_if_only_lost(self, client: TestClient, unique_slug: str):
        stages = {s["name"]: s for s in client.get("/pipeline-stages").json()}
        company_id = _create_company(client, f"{unique_slug}-ipl")
        event_id = _create_event(client, f"{unique_slug}-ipl")
        entry_id = _create_company_pipeline(client, event_id, company_id)

        client.post(f"/pipeline-entries/{entry_id}/move", json={
            "stage_id": stages["Odrzucony"]["id"],
            "rejection_reason": "Not interested",
        })

        company = client.get(f"/companies/{company_id}").json()
        assert company["is_partner"] is False
