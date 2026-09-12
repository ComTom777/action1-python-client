"""``/endpoints/groups`` and group membership."""

from __future__ import annotations

from typing import Any, Iterable


class EndpointGroupsMixin:
    def list_endpoint_groups(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/endpoints/groups/{org_id}"))

    def get_endpoint_group(self, org_id: str, group_id: str) -> dict:
        return self.get(f"/endpoints/groups/{org_id}/{group_id}")

    def create_endpoint_group(self, org_id: str, **fields: Any) -> dict:
        return self.post(f"/endpoints/groups/{org_id}", json=fields)

    def update_endpoint_group(self, org_id: str, group_id: str, **fields: Any) -> dict:
        return self.patch(f"/endpoints/groups/{org_id}/{group_id}", json=fields)

    def delete_endpoint_group(self, org_id: str, group_id: str) -> None:
        self.delete(f"/endpoints/groups/{org_id}/{group_id}")

    def list_endpoint_group_members(self, org_id: str, group_id: str) -> list[dict]:
        return list(self.paginate(f"/endpoints/groups/{org_id}/{group_id}/contents"))

    def add_endpoint_group_members(
        self, org_id: str, group_id: str, endpoint_ids: Iterable[str]
    ) -> Any:
        body = [
            {"method": "POST", "data": {"endpoint_id": eid, "type": "Endpoint"}}
            for eid in endpoint_ids
        ]
        return self.post(f"/endpoints/groups/{org_id}/{group_id}/contents", json=body)

    def remove_endpoint_group_members(
        self, org_id: str, group_id: str, endpoint_ids: Iterable[str]
    ) -> Any:
        body = [{"method": "DELETE", "endpoint_id": eid} for eid in endpoint_ids]
        return self.post(f"/endpoints/groups/{org_id}/{group_id}/contents", json=body)
