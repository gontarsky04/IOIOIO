"""Tests for /contacts CRUD endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _get_valid_company_id(client: TestClient) -> int:
    """Get a company with valid contacts (to avoid seeded invalid emails)."""
    companies_r = client.get("/companies?page=1&page_size=1")
    return companies_r.json()["items"][0]["id"]


class TestContactsList:
    def test_list_contacts_filtered_by_company(self, client: TestClient):
        company_id = _get_valid_company_id(client)
        r = client.get(f"/contacts?company_id={company_id}")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "first_name" in data[0]
        assert "last_name" in data[0]
        assert "company_id" in data[0]
        for contact in data:
            assert contact["company_id"] == company_id

    def test_list_contacts_nonexistent_company_returns_empty(self, client: TestClient):
        r = client.get("/contacts?company_id=999999")
        assert r.status_code == 200
        assert r.json() == []


class TestContactsCreate:
    def test_create_contact_success(self, client: TestClient, unique_slug: str):
        company_id = _get_valid_company_id(client)
        payload = {
            "first_name": f"Jan-{unique_slug}",
            "last_name": f"Kowalski-{unique_slug}",
            "company_id": company_id,
            "position": "CTO",
            "email": f"jan.{unique_slug}@example.com",
            "phone": "+48123456789",
        }
        r = client.post("/contacts", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["first_name"] == payload["first_name"]
        assert data["last_name"] == payload["last_name"]
        assert data["company_id"] == company_id
        assert data["position"] == "CTO"
        assert data["email"] == payload["email"]
        assert "id" in data
        assert "created_at" in data

    def test_create_contact_missing_company_returns_404(self, client: TestClient, unique_slug: str):
        payload = {
            "first_name": f"Anna-{unique_slug}",
            "last_name": "Nowak",
            "company_id": 999999,
        }
        r = client.post("/contacts", json=payload)
        assert r.status_code == 404

    def test_create_contact_missing_first_name_returns_422(self, client: TestClient):
        company_id = _get_valid_company_id(client)
        payload = {
            "last_name": "Nowak",
            "company_id": company_id,
        }
        r = client.post("/contacts", json=payload)
        assert r.status_code == 422

    def test_create_contact_empty_first_name_returns_422(self, client: TestClient):
        company_id = _get_valid_company_id(client)
        payload = {
            "first_name": "",
            "last_name": "Nowak",
            "company_id": company_id,
        }
        r = client.post("/contacts", json=payload)
        assert r.status_code == 422

    def test_create_contact_invalid_email_returns_422(self, client: TestClient):
        company_id = _get_valid_company_id(client)
        payload = {
            "first_name": "Anna",
            "last_name": "Nowak",
            "company_id": company_id,
            "email": "not-an-email",
        }
        r = client.post("/contacts", json=payload)
        assert r.status_code == 422


class TestContactsGetById:
    def test_get_contact_success(self, client: TestClient, unique_slug: str):
        company_id = _get_valid_company_id(client)
        create_r = client.post("/contacts", json={
            "first_name": f"Get-{unique_slug}",
            "last_name": "Test",
            "company_id": company_id,
            "email": f"get.{unique_slug}@example.com",
        })
        contact_id = create_r.json()["id"]
        r = client.get(f"/contacts/{contact_id}")
        assert r.status_code == 200
        assert r.json()["id"] == contact_id

    def test_get_contact_not_found(self, client: TestClient):
        r = client.get("/contacts/999999")
        assert r.status_code == 404


class TestContactsUpdate:
    def test_update_contact_partial(self, client: TestClient, unique_slug: str):
        company_id = _get_valid_company_id(client)
        create_r = client.post("/contacts", json={
            "first_name": f"Upd-{unique_slug}",
            "last_name": "Test",
            "company_id": company_id,
        })
        contact_id = create_r.json()["id"]
        new_position = f"Director-{unique_slug}"
        r = client.patch(f"/contacts/{contact_id}", json={"position": new_position})
        assert r.status_code == 200
        assert r.json()["position"] == new_position

    def test_update_contact_not_found(self, client: TestClient):
        r = client.patch("/contacts/999999", json={"position": "CEO"})
        assert r.status_code == 404


class TestContactsDelete:
    def test_delete_contact_success(self, client: TestClient, unique_slug: str):
        company_id = _get_valid_company_id(client)
        create_r = client.post("/contacts", json={
            "first_name": f"Del-{unique_slug}",
            "last_name": "Tester",
            "company_id": company_id,
        })
        contact_id = create_r.json()["id"]
        r = client.delete(f"/contacts/{contact_id}")
        assert r.status_code == 204
        get_r = client.get(f"/contacts/{contact_id}")
        assert get_r.status_code == 404

    def test_delete_contact_not_found(self, client: TestClient):
        r = client.delete("/contacts/999999")
        assert r.status_code == 404
