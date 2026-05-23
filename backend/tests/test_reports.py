"""Tests for /reports endpoint and CSV export."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestReportsSummary:
    def test_reports_returns_expected_shape(self, client: TestClient):
        r = client.get("/reports")
        assert r.status_code == 200
        data = r.json()
        assert "totals" in data
        assert "annual" in data
        assert "events" in data
        assert "pipeline_stages" in data
        assert "company_history" in data
        assert "new_sponsors" in data
        assert "top_companies" in data
        assert "yearly_trends" in data

    def test_reports_totals_shape(self, client: TestClient):
        r = client.get("/reports")
        totals = r.json()["totals"]
        assert "partners_count" in totals
        assert "total_value" in totals
        assert "pipeline_count" in totals
        assert "conversion_rate" in totals

    def test_reports_filter_by_year(self, client: TestClient):
        r = client.get("/reports?year=2026")
        assert r.status_code == 200
        data = r.json()
        assert "totals" in data

    def test_reports_filter_by_nonexistent_year(self, client: TestClient):
        r = client.get("/reports?year=2099")
        assert r.status_code == 200
        totals = r.json()["totals"]
        assert totals["partners_count"] == 0

    def test_reports_filter_by_industry(self, client: TestClient):
        industries_r = client.get("/industries")
        industry_id = industries_r.json()[0]["id"]
        r = client.get(f"/reports?industry_id={industry_id}")
        assert r.status_code == 200

    def test_reports_filter_by_owner(self, client: TestClient):
        users_r = client.get("/users")
        user_id = users_r.json()[0]["id"]
        r = client.get(f"/reports?owner_user_id={user_id}")
        assert r.status_code == 200

    def test_reports_filter_by_event(self, client: TestClient):
        events_r = client.get("/events?page=1&page_size=1")
        event_id = events_r.json()["items"][0]["id"]
        r = client.get(f"/reports?event_id={event_id}")
        assert r.status_code == 200

    def test_reports_filter_by_company(self, client: TestClient):
        companies_r = client.get("/companies?page=1&page_size=1")
        company_id = companies_r.json()["items"][0]["id"]
        r = client.get(f"/reports?company_id={company_id}")
        assert r.status_code == 200

    def test_reports_year_validation(self, client: TestClient):
        r = client.get("/reports?year=1999")
        assert r.status_code == 422
        r = client.get("/reports?year=2101")
        assert r.status_code == 422


class TestReportsExportCSV:
    def test_csv_export_returns_csv(self, client: TestClient):
        r = client.get("/reports/export.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "reports.csv" in r.headers.get("content-disposition", "")

    def test_csv_export_has_header_rows(self, client: TestClient):
        r = client.get("/reports/export.csv")
        lines = r.text.strip().split("\n")
        assert len(lines) >= 1
        assert "Sekcja" in lines[0]

    def test_csv_export_with_filters(self, client: TestClient):
        r = client.get("/reports/export.csv?year=2026")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]

    def test_csv_export_year_validation(self, client: TestClient):
        r = client.get("/reports/export.csv?year=1999")
        assert r.status_code == 422
