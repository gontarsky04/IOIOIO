"""Tests for /users endpoint, upload validation, and invoice edge cases."""
from __future__ import annotations

import io
from datetime import date

import pytest
from fastapi.testclient import TestClient


class TestUsersEndpoints:
    def test_list_users(self, client: TestClient):
        r = client.get("/users")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "first_name" in data[0]
        assert "last_name" in data[0]
        assert "role" in data[0]

    def test_list_users_filter_by_role(self, client: TestClient):
        r = client.get("/users?role=koordynator")
        assert r.status_code == 200
        for user in r.json():
            assert user["role"]["name"] == "koordynator"

    def test_list_users_active_only_default(self, client: TestClient):
        r = client.get("/users")
        for user in r.json():
            assert user["is_active"] is True

    def test_list_users_include_inactive(self, client: TestClient):
        r = client.get("/users?active_only=false")
        assert r.status_code == 200

    def test_get_user_by_id(self, client: TestClient):
        users_r = client.get("/users")
        user_id = users_r.json()[0]["id"]
        r = client.get(f"/users/{user_id}")
        assert r.status_code == 200
        assert r.json()["id"] == user_id
        assert "email" in r.json()
        assert "role" in r.json()

    def test_get_user_not_found(self, client: TestClient):
        r = client.get("/users/999999")
        assert r.status_code == 404


class TestUploadValidation:
    def _upload(self, client, filename, content_type):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        return client.post(
            f"/companies/{company_id}/documents/upload",
            files={"file": (filename, io.BytesIO(b"content"), content_type)},
        )

    def test_allowed_pdf(self, client: TestClient):
        r = self._upload(client, "doc.pdf", "application/pdf")
        assert r.status_code == 201

    def test_allowed_docx(self, client: TestClient):
        r = self._upload(
            client, "doc.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert r.status_code == 201

    def test_allowed_xlsx(self, client: TestClient):
        r = self._upload(
            client, "data.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert r.status_code == 201

    def test_allowed_pptx(self, client: TestClient):
        r = self._upload(
            client, "pres.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        assert r.status_code == 201

    def test_allowed_zip(self, client: TestClient):
        r = self._upload(client, "archive.zip", "application/zip")
        assert r.status_code == 201

    def test_allowed_txt(self, client: TestClient):
        r = self._upload(client, "notes.txt", "text/plain")
        assert r.status_code == 201

    def test_rejected_exe(self, client: TestClient):
        r = self._upload(client, "virus.exe", "application/x-msdownload")
        assert r.status_code == 400

    def test_rejected_js(self, client: TestClient):
        r = self._upload(client, "script.js", "application/javascript")
        assert r.status_code == 400

    def test_rejected_html(self, client: TestClient):
        r = self._upload(client, "page.html", "text/html")
        assert r.status_code == 400

    def test_allowed_by_extension_octet_stream(self, client: TestClient):
        r = self._upload(client, "doc.pdf", "application/octet-stream")
        assert r.status_code == 201

    def test_rejected_unknown_extension_unknown_mime(self, client: TestClient):
        r = self._upload(client, "file.xyz", "application/x-unknown")
        assert r.status_code == 400


class TestInvoiceEdgeCases:
    def _create_invoice(self, client, slug, **kwargs):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        payload = {
            "invoice_number": f"INV-{slug}",
            "company_id": company_id,
            "event_id": event_id,
            "amount": 5000,
            "currency": "PLN",
            "issue_date": "2026-05-01",
            "due_date": "2026-06-01",
            "payment_status": "pending",
            **kwargs,
        }
        return client.post("/invoices", json=payload)

    def test_create_invoice_paid_at_without_paid_status_returns_422(self, client: TestClient, unique_slug: str):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        payload = {
            "invoice_number": f"INV-{unique_slug}",
            "company_id": company_id,
            "event_id": event_id,
            "amount": 5000,
            "currency": "PLN",
            "issue_date": "2026-05-01",
            "due_date": "2026-06-01",
            "payment_status": "pending",
            "paid_at": "2026-05-15",
        }
        r = client.post("/invoices", json=payload)
        assert r.status_code == 422

    def test_create_invoice_paid_with_paid_at_success(self, client: TestClient, unique_slug: str):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        payload = {
            "invoice_number": f"INV-PAID-{unique_slug}",
            "company_id": company_id,
            "event_id": event_id,
            "amount": 5000,
            "currency": "PLN",
            "issue_date": "2026-05-01",
            "due_date": "2026-06-01",
            "payment_status": "paid",
            "paid_at": "2026-05-15",
        }
        r = client.post("/invoices", json=payload)
        assert r.status_code == 201
        assert r.json()["payment_status"] == "paid"
        assert r.json()["paid_at"] is not None

    def test_delete_invoice(self, client: TestClient, unique_slug: str):
        r = self._create_invoice(client, unique_slug)
        invoice_id = r.json()["id"]
        del_r = client.delete(f"/invoices/{invoice_id}")
        assert del_r.status_code == 204
        get_r = client.get(f"/invoices/{invoice_id}")
        assert get_r.status_code == 404

    def test_delete_invoice_not_found(self, client: TestClient):
        r = client.delete("/invoices/999999")
        assert r.status_code == 404

    def test_get_invoice_not_found(self, client: TestClient):
        r = client.get("/invoices/999999")
        assert r.status_code == 404

    def test_update_invoice_clears_paid_at_when_status_changes(self, client: TestClient, unique_slug: str):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        create_r = client.post("/invoices", json={
            "invoice_number": f"INV-CLR-{unique_slug}",
            "company_id": company_id,
            "event_id": event_id,
            "amount": 8000,
            "currency": "PLN",
            "issue_date": "2026-05-01",
            "due_date": "2026-06-01",
            "payment_status": "paid",
            "paid_at": "2026-05-20",
        })
        invoice_id = create_r.json()["id"]
        r = client.patch(f"/invoices/{invoice_id}", json={"payment_status": "pending"})
        assert r.status_code == 200
        assert r.json()["paid_at"] is None

    def test_update_invoice_company_not_found(self, client: TestClient, unique_slug: str):
        r = self._create_invoice(client, unique_slug)
        invoice_id = r.json()["id"]
        r = client.patch(f"/invoices/{invoice_id}", json={"company_id": 999999})
        assert r.status_code == 404

    def test_create_invoice_invalid_payment_status(self, client: TestClient):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        payload = {
            "invoice_number": "BAD",
            "company_id": company_id,
            "amount": 1000,
            "currency": "PLN",
            "issue_date": "2026-05-01",
            "due_date": "2026-06-01",
            "payment_status": "invalid_status",
        }
        r = client.post("/invoices", json=payload)
        assert r.status_code == 422


class TestCompanyEndpointsExtended:
    def test_get_company_by_id(self, client: TestClient):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        r = client.get(f"/companies/{company_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == company_id
        assert "is_partner" in data
        assert "industry" in data
        assert "tags" in data

    def test_get_company_not_found(self, client: TestClient):
        r = client.get("/companies/999999")
        assert r.status_code == 404

    def test_patch_company(self, client: TestClient, unique_slug: str):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        r = client.patch(f"/companies/{company_id}", json={"city": f"City-{unique_slug}"})
        assert r.status_code == 200
        assert r.json()["city"] == f"City-{unique_slug}"

    def test_patch_company_not_found(self, client: TestClient):
        r = client.patch("/companies/999999", json={"city": "X"})
        assert r.status_code == 404

    def test_company_events_endpoint(self, client: TestClient):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        r = client.get(f"/companies/{company_id}/events")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_company_activities_endpoint(self, client: TestClient):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        r = client.get(f"/companies/{company_id}/activities")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_company_report_endpoint(self, client: TestClient):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        r = client.get(f"/companies/{company_id}/report")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)
