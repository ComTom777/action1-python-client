"""``/installed-software``."""

from __future__ import annotations


class InstalledSoftwareMixin:
    def list_installed_software(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/installed-software/{org_id}/data"))

    def list_endpoint_installed_software(self, org_id: str, endpoint_id: str) -> list[dict]:
        return list(self.paginate(f"/installed-software/{org_id}/data/{endpoint_id}"))

    def list_installed_software_errors(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/installed-software/{org_id}/errors"))

    def requery_installed_software(self, org_id: str) -> None:
        """Re-queries installed software across every managed endpoint in the organization."""
        self.post(f"/installed-software/{org_id}/requery")

    def requery_endpoint_installed_software(self, org_id: str, endpoint_id: str) -> None:
        self.post(f"/installed-software/{org_id}/requery/{endpoint_id}")
