"""Tests for /company-relationships CRUD endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _get_ids(client: TestClient) -> tuple[int, int]:
    """Return a valid company_id and relationship_type_id."""
    companies_r = client.get("/companies?page=1&page_size=1")
    company_id = companies_r.json()["items"][0]["id"]
    types_r = client.get("/relationship-types")
    rel_type_id = types_r.json()[0]["id"]
    return company_id, rel_type_id


class TestCompanyRelationshipsList:
    def test_list_all(self, client: TestClient):
        r = client.get("/company-relationships")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_filter_by_company(self, client: TestClient):
        company_id, _ = _get_ids(client)
        r = client.get(f"/company-relationships?company_id={company_id}")
        assert r.status_code == 200
        for rel in r.json():
            assert rel["company_id"] == company_id

    def test_list_filter_by_event(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        r = client.get(f"/company-relationships?event_id={event_id}")
        assert r.status_code == 200
        for rel in r.json():
            assert rel["event_id"] == event_id

    def test_list_filter_by_status(self, client: TestClient):
        r = client.get("/company-relationships?status=draft")
        assert r.status_code == 200
        for rel in r.json():
            assert rel["status"] == "draft"


class TestCompanyRelationshipsCreate:
    def test_create_relationship_success(self, client: TestClient, unique_slug: str):
        company_id, rel_type_id = _get_ids(client)
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        payload = {
            "company_id": company_id,
            "event_id": event_id,
            "relationship_type_id": rel_type_id,
            "package_name": f"Gold-{unique_slug}",
            "amount_net": 10000,
            "amount_gross": 12300,
            "currency": "PLN",
            "status": "draft",
        }
        r = client.post("/company-relationships", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["company_id"] == company_id
        assert data["relationship_type_id"] == rel_type_id
        assert data["package_name"] == payload["package_name"]
        assert float(data["amount_net"]) == 10000

    def test_create_relationship_company_not_found(self, client: TestClient):
        _, rel_type_id = _get_ids(client)
        payload = {
            "company_id": 999999,
            "relationship_type_id": rel_type_id,
            "status": "draft",
        }
        r = client.post("/company-relationships", json=payload)
        assert r.status_code == 404

    def test_create_relationship_type_not_found(self, client: TestClient):
        company_id, _ = _get_ids(client)
        payload = {
            "company_id": company_id,
            "relationship_type_id": 999999,
            "status": "draft",
        }
        r = client.post("/company-relationships", json=payload)
        assert r.status_code == 404


class TestCompanyRelationshipsGetById:
    def test_get_relationship_success(self, client: TestClient):
        rels_r = client.get("/company-relationships")
        if rels_r.json():
            rel_id = rels_r.json()[0]["id"]
            r = client.get(f"/company-relationships/{rel_id}")
            assert r.status_code == 200
            assert r.json()["id"] == rel_id

    def test_get_relationship_not_found(self, client: TestClient):
        r = client.get("/company-relationships/999999")
        assert r.status_code == 404


class TestCompanyRelationshipsUpdate:
    def test_update_relationship_status(self, client: TestClient, unique_slug: str):
        company_id, rel_type_id = _get_ids(client)
        create_r = client.post("/company-relationships", json={
            "company_id": company_id,
            "relationship_type_id": rel_type_id,
            "status": "draft",
            "package_name": f"Upd-{unique_slug}",
        })
        rel_id = create_r.json()["id"]
        r = client.patch(
            f"/company-relationships/{rel_id}", json={"status": "active"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    def test_update_relationship_amount(self, client: TestClient, unique_slug: str):
        company_id, rel_type_id = _get_ids(client)
        create_r = client.post("/company-relationships", json={
            "company_id": company_id,
            "relationship_type_id": rel_type_id,
            "status": "draft",
            "amount_net": 5000,
        })
        rel_id = create_r.json()["id"]
        r = client.patch(f"/company-relationships/{rel_id}", json={"amount_net": 15000})
        assert r.status_code == 200
        assert float(r.json()["amount_net"]) == 15000

    def test_update_relationship_not_found(self, client: TestClient):
        r = client.patch("/company-relationships/999999", json={"status": "active"})
        assert r.status_code == 404


class TestCompanyRelationshipsDelete:
    def test_delete_relationship(self, client: TestClient, unique_slug: str):
        company_id, rel_type_id = _get_ids(client)
        create_r = client.post("/company-relationships", json={
            "company_id": company_id,
            "relationship_type_id": rel_type_id,
            "status": "draft",
        })
        rel_id = create_r.json()["id"]
        r = client.delete(f"/company-relationships/{rel_id}")
        assert r.status_code == 204
        get_r = client.get(f"/company-relationships/{rel_id}")
        assert get_r.status_code == 404

    def test_delete_relationship_not_found(self, client: TestClient):
        r = client.delete("/company-relationships/999999")
        assert r.status_code == 404
