"""``/updates`` (missing OS/third-party updates and approvals)."""

from __future__ import annotations

from typing import Any


class UpdatesMixin:
    def list_missing_updates(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/updates/{org_id}"))

    def get_update_package(self, org_id: str, package_id: str) -> dict:
        return self.get(f"/updates/{org_id}/{package_id}")

    def list_update_missing_endpoints(
        self, org_id: str, package_id: str, version_id: str
    ) -> list[dict]:
        return list(
            self.paginate(f"/updates/{org_id}/{package_id}/versions/{version_id}/endpoints")
        )

    def set_update_approvals(self, org_id: str, approvals: list[dict[str, Any]]) -> Any:
        """``approvals``: list of ``{"approval_status": "Approved"|"Declined"|"New", "packages": [...]}``."""
        return self.post(f"/updates/{org_id}/approvals", json=approvals)
