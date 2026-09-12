"""``/organizations``."""

from __future__ import annotations

from typing import Any


class OrganizationsMixin:
    def list_organizations(self) -> list[dict]:
        return list(self.paginate("/organizations"))

    def get_organization(self, org_id: str) -> dict:
        return self.get(f"/organizations/{org_id}")

    def create_organization(self, name: str, description: str = "") -> dict:
        return self.post("/organizations", json={"name": name, "description": description})

    def update_organization(self, org_id: str, **fields: Any) -> dict:
        return self.patch(f"/organizations/{org_id}", json=fields)

    def delete_organization(self, org_id: str) -> None:
        self.delete(f"/organizations/{org_id}")

    def search(self, org_id: str, query: str, *, limit: int | None = None) -> list[dict]:
        params: dict[str, Any] = {"query": query}
        if limit is not None:
            params["limit"] = limit
        return list(self.paginate(f"/search/{org_id}", params=params))
