"""``/reports/all`` (report/category catalog) and ``/reportdata`` (report execution results)."""

from __future__ import annotations

from typing import Any


class ReportsMixin:
    def list_reports(self) -> list[dict]:
        return list(self.paginate("/reports/all"))

    def get_report_or_category(self, report_or_category_id: str) -> dict:
        return self.get(f"/reports/all/{report_or_category_id}")

    def create_custom_report(self, **fields: Any) -> dict:
        return self.post("/reports/all/custom", json=fields)

    def create_simple_report(
        self, name: str, data_source: dict, columns: list[str], *, description: str = ""
    ) -> dict:
        """Custom report showing ``columns`` of one data source (as returned by
        ``publish_data_source``). Every field below is required by the API: ``data_sources``
        must be "/API/data_sources/all/<id>" strings ({"id", "self"} objects 500 as of
        2026-10), ``filter_set`` needs >= 1 filter, and the empty lists must be present."""
        ds_id = data_source["id"]
        return self.create_custom_report(
            name=name,
            description=description,
            data_sources=[f"/API/data_sources/all/{ds_id}"],
            simple_columns=[
                {"name": c, "enabled": "yes", "sort": "none", "data_source_id": ds_id}
                for c in columns
            ],
            summary_columns=[],
            drilldown_columns=[],
            filter_set={
                "filters": [
                    {"name": "Endpoint Name", "value": "*", "operator": "=", "data_source_id": ds_id}
                ],
                "filter_logic": "",
            },
            column_aliases=[],
        )

    def update_custom_report(self, report_id: str, **fields: Any) -> dict:
        return self.patch(f"/reports/all/custom/{report_id}", json=fields)

    def delete_custom_report(self, report_id: str) -> None:
        self.delete(f"/reports/all/custom/{report_id}")

    def list_report_data(self, org_id: str, report_id: str) -> list[dict]:
        return list(self.paginate(f"/reportdata/{org_id}/{report_id}/data"))

    def list_report_errors(self, org_id: str, report_id: str) -> list[dict]:
        return list(self.paginate(f"/reportdata/{org_id}/{report_id}/errors"))

    def export_report(self, org_id: str, report_id: str) -> Any:
        return self.get(f"/reportdata/{org_id}/{report_id}/export")

    def requery_report(self, org_id: str, report_id: str) -> None:
        self.post(f"/reportdata/{org_id}/{report_id}/requery")

    def get_report_row_drilldown(self, org_id: str, report_id: str, row_id: str) -> list[dict]:
        return list(
            self.paginate(f"/reportdata/{org_id}/{report_id}/data/{row_id}/drilldown")
        )

    def export_report_row(self, org_id: str, report_id: str, row_id: str) -> Any:
        return self.get(f"/reportdata/{org_id}/{report_id}/data/{row_id}/export")
