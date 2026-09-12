"""``/vulnerabilities`` and ``/CVE-descriptions``."""

from __future__ import annotations

from typing import Any


class VulnerabilitiesMixin:
    def list_vulnerabilities(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/vulnerabilities/{org_id}"))

    def get_vulnerability(self, org_id: str, cve_id: str) -> dict:
        return self.get(f"/vulnerabilities/{org_id}/{cve_id}")

    def list_vulnerability_endpoints(self, org_id: str, cve_id: str) -> list[dict]:
        return list(self.paginate(f"/vulnerabilities/{org_id}/{cve_id}/endpoints"))

    def get_cve_description(self, cve_id: str) -> dict:
        """General CVE information (attack vector etc.), not scoped to an organization."""
        return self.get(f"/CVE-descriptions/{cve_id}")

    # -- Compensating-control remediations --

    def list_vulnerability_remediations(self, org_id: str, cve_id: str) -> list[dict]:
        return list(self.paginate(f"/vulnerabilities/{org_id}/{cve_id}/remediations"))

    def create_vulnerability_remediation(self, org_id: str, cve_id: str, **fields: Any) -> dict:
        return self.post(f"/vulnerabilities/{org_id}/{cve_id}/remediations", json=fields)

    def update_vulnerability_remediation(
        self, org_id: str, cve_id: str, remediation_id: str, **fields: Any
    ) -> dict:
        return self.patch(
            f"/vulnerabilities/{org_id}/{cve_id}/remediations/{remediation_id}", json=fields
        )

    def delete_vulnerability_remediation(
        self, org_id: str, cve_id: str, remediation_id: str
    ) -> None:
        self.delete(f"/vulnerabilities/{org_id}/{cve_id}/remediations/{remediation_id}")
