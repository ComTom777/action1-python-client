"""``/enterprise`` (account-level settings) and ``/subscription`` (licensing/usage)."""

from __future__ import annotations

from typing import Any


class EnterpriseMixin:
    def get_enterprise(self) -> dict:
        return self.get("/enterprise")

    def update_enterprise(self, **fields: Any) -> dict:
        return self.patch("/enterprise", json=fields)

    def request_enterprise_closure(self, **fields: Any) -> Any:
        """Closes the entire Action1 account. Irreversible without a follow-up revoke."""
        return self.post("/enterprise/request-closure", json=fields or None)

    def revoke_enterprise_closure(self) -> Any:
        return self.post("/enterprise/revoke-closure")

    def get_enterprise_license(self) -> dict:
        return self.get("/subscription/enterprise")

    def request_enterprise_trial(self, **fields: Any) -> Any:
        return self.post("/subscription/enterprise/trial", json=fields or None)

    def request_enterprise_quote(self, **fields: Any) -> Any:
        return self.post("/subscription/enterprise/quote", json=fields or None)

    def get_enterprise_usage(self) -> dict:
        return self.get("/subscription/usage/enterprise")

    def list_organizations_usage(self) -> list[dict]:
        return list(self.paginate("/subscription/usage/organizations"))

    def get_organization_usage(self, org_id: str) -> dict:
        return self.get(f"/subscription/usage/organizations/{org_id}")
