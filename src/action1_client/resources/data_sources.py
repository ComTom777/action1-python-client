"""``/data-sources/all`` (external data source integrations)."""

from __future__ import annotations

from typing import Any


class DataSourcesMixin:
    def list_data_sources(self) -> list[dict]:
        return list(self.paginate("/data-sources/all"))

    def get_data_source(self, data_source_id: str) -> dict:
        return self.get(f"/data-sources/all/{data_source_id}")

    def create_data_source(self, **fields: Any) -> dict:
        return self.post("/data-sources/all", json=fields)

    def update_data_source(self, data_source_id: str, **fields: Any) -> dict:
        return self.patch(f"/data-sources/all/{data_source_id}", json=fields)

    def delete_data_source(self, data_source_id: str) -> None:
        self.delete(f"/data-sources/all/{data_source_id}")

    def publish_data_source(
        self,
        name: str,
        script_text: str,
        columns: list[str],
        *,
        description: str = "",
        data_source_id: str | None = None,
    ) -> dict:
        """Create (or update in place, if ``data_source_id``) a published PowerShell data source.

        Creating with real columns 400s ("columns ... must be empty for 'Draft' status"), so it's
        two calls: create as an empty Draft, then PATCH in the columns and publish.
        """
        if data_source_id:
            return self.update_data_source(data_source_id, script_text=script_text, columns=columns)
        draft = self.create_data_source(
            name=name, description=description, language="PowerShell",
            script_text=script_text, columns=[], status="Draft",
        )
        return self.update_data_source(draft["id"], columns=columns, status="Published")
