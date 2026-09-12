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
