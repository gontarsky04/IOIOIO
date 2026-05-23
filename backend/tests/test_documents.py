"""Tests for document endpoints (company docs and event-company docs)."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient


def _get_company_id(client: TestClient) -> int:
    r = client.get("/companies?page=1&page_size=1")
    return r.json()["items"][0]["id"]


def _get_event_and_company(client: TestClient) -> tuple[int, int]:
    events_r = client.get("/events?page=1&page_size=1")
    event_id = events_r.json()["items"][0]["id"]
    pipeline_r = client.get(f"/events/{event_id}/pipeline")
    entries = pipeline_r.json()
    if entries:
        return event_id, entries[0]["company"]["id"]
    companies_r = client.get("/companies?page=1&page_size=1")
    return event_id, companies_r.json()["items"][0]["id"]


class TestCompanyDocumentsCreate:
    def test_create_document_metadata(self, client: TestClient, unique_slug: str):
        company_id = _get_company_id(client)
        payload = {
            "file_name": f"contract-{unique_slug}.pdf",
            "file_url": f"/storage/documents/{unique_slug}.pdf",
            "document_type": "contract",
        }
        r = client.post(f"/companies/{company_id}/documents", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["file_name"] == payload["file_name"]
        assert data["file_url"] == payload["file_url"]
        assert data["document_type"] == "contract"
        assert data["archived"] is False

    def test_create_document_company_not_found(self, client: TestClient):
        payload = {
            "file_name": "test.pdf",
            "file_url": "/storage/documents/test.pdf",
        }
        r = client.post("/companies/999999/documents", json=payload)
        assert r.status_code == 404

    def test_create_document_missing_file_name_returns_422(self, client: TestClient):
        company_id = _get_company_id(client)
        payload = {"file_url": "/storage/documents/test.pdf"}
        r = client.post(f"/companies/{company_id}/documents", json=payload)
        assert r.status_code == 422


class TestCompanyDocumentsList:
    def test_list_documents_excludes_archived(self, client: TestClient, unique_slug: str):
        company_id = _get_company_id(client)
        client.post(f"/companies/{company_id}/documents", json={
            "file_name": f"archived-{unique_slug}.pdf",
            "file_url": f"/storage/documents/a-{unique_slug}.pdf",
        })
        r = client.get(f"/companies/{company_id}/documents")
        assert r.status_code == 200
        data = r.json()
        for doc in data:
            assert doc["archived"] is False

    def test_list_documents_include_archived(self, client: TestClient):
        company_id = _get_company_id(client)
        r = client.get(f"/companies/{company_id}/documents?include_archived=true")
        assert r.status_code == 200


class TestCompanyDocumentsUpload:
    def test_upload_valid_pdf(self, client: TestClient):
        company_id = _get_company_id(client)
        file_content = b"%PDF-1.4 fake content"
        r = client.post(
            f"/companies/{company_id}/documents/upload",
            files={"file": ("report.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["file_name"] == "report.pdf"
        assert "/storage/documents/" in data["file_url"]

    def test_upload_valid_image(self, client: TestClient):
        company_id = _get_company_id(client)
        file_content = b"\x89PNG\r\n\x1a\n fake png"
        r = client.post(
            f"/companies/{company_id}/documents/upload",
            files={"file": ("logo.png", io.BytesIO(file_content), "image/png")},
        )
        assert r.status_code == 201

    def test_upload_invalid_mime_and_extension_returns_400(self, client: TestClient):
        company_id = _get_company_id(client)
        file_content = b"executable content"
        r = client.post(
            f"/companies/{company_id}/documents/upload",
            files={"file": ("malware.exe", io.BytesIO(file_content), "application/x-executable")},
        )
        assert r.status_code == 400

    def test_upload_allowed_by_extension_even_if_mime_unknown(self, client: TestClient):
        company_id = _get_company_id(client)
        file_content = b"some csv data"
        r = client.post(
            f"/companies/{company_id}/documents/upload",
            files={"file": ("data.csv", io.BytesIO(file_content), "application/octet-stream")},
        )
        assert r.status_code == 201


class TestCompanyDocumentsArchive:
    def test_archive_and_unarchive(self, client: TestClient, unique_slug: str):
        company_id = _get_company_id(client)
        create_r = client.post(f"/companies/{company_id}/documents", json={
            "file_name": f"archiveable-{unique_slug}.pdf",
            "file_url": f"/storage/documents/ar-{unique_slug}.pdf",
        })
        doc_id = create_r.json()["id"]

        r = client.post(f"/companies/{company_id}/documents/{doc_id}/archive")
        assert r.status_code == 200
        assert r.json()["archived"] is True

        r = client.post(f"/companies/{company_id}/documents/{doc_id}/unarchive")
        assert r.status_code == 200
        assert r.json()["archived"] is False

    def test_archive_not_found(self, client: TestClient):
        company_id = _get_company_id(client)
        r = client.post(f"/companies/{company_id}/documents/999999/archive")
        assert r.status_code == 404


class TestCompanyDocumentsDelete:
    def test_delete_document(self, client: TestClient, unique_slug: str):
        company_id = _get_company_id(client)
        create_r = client.post(f"/companies/{company_id}/documents", json={
            "file_name": f"todelete-{unique_slug}.pdf",
            "file_url": f"/storage/documents/del-{unique_slug}.pdf",
        })
        doc_id = create_r.json()["id"]
        r = client.delete(f"/companies/{company_id}/documents/{doc_id}")
        assert r.status_code == 204

    def test_delete_document_not_found(self, client: TestClient):
        company_id = _get_company_id(client)
        r = client.delete(f"/companies/{company_id}/documents/999999")
        assert r.status_code == 404


class TestEventCompanyDocuments:
    def test_list_event_company_documents(self, client: TestClient):
        event_id, company_id = _get_event_and_company(client)
        r = client.get(f"/events/{event_id}/companies/{company_id}/documents")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_event_company_document(self, client: TestClient, unique_slug: str):
        event_id, company_id = _get_event_and_company(client)
        payload = {
            "file_name": f"event-doc-{unique_slug}.pdf",
            "file_url": f"/storage/documents/ev-{unique_slug}.pdf",
            "document_type": "offer",
        }
        r = client.post(
            f"/events/{event_id}/companies/{company_id}/documents", json=payload
        )
        assert r.status_code == 201
        data = r.json()
        assert data["file_name"] == payload["file_name"]

    def test_upload_event_company_document(self, client: TestClient):
        event_id, company_id = _get_event_and_company(client)
        file_content = b"%PDF-1.4 content"
        r = client.post(
            f"/events/{event_id}/companies/{company_id}/documents/upload",
            files={"file": ("offer.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert r.status_code == 201

    def test_delete_event_company_document(self, client: TestClient, unique_slug: str):
        event_id, company_id = _get_event_and_company(client)
        create_r = client.post(
            f"/events/{event_id}/companies/{company_id}/documents",
            json={
                "file_name": f"evdel-{unique_slug}.pdf",
                "file_url": f"/storage/documents/evdel-{unique_slug}.pdf",
            },
        )
        doc_id = create_r.json()["id"]
        r = client.delete(
            f"/events/{event_id}/companies/{company_id}/documents/{doc_id}"
        )
        assert r.status_code == 204

    def test_archive_event_company_document(self, client: TestClient, unique_slug: str):
        event_id, company_id = _get_event_and_company(client)
        create_r = client.post(
            f"/events/{event_id}/companies/{company_id}/documents",
            json={
                "file_name": f"evar-{unique_slug}.pdf",
                "file_url": f"/storage/documents/evar-{unique_slug}.pdf",
            },
        )
        doc_id = create_r.json()["id"]
        r = client.post(
            f"/events/{event_id}/companies/{company_id}/documents/{doc_id}/archive"
        )
        assert r.status_code == 200
        assert r.json()["archived"] is True

    def test_event_not_found(self, client: TestClient):
        r = client.get("/events/999999/companies/1/documents")
        assert r.status_code == 404

    def test_company_not_found(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        r = client.get(f"/events/{event_id}/companies/999999/documents")
        assert r.status_code == 404
