"""``/audit`` (user action audit trail) and ``/logs`` (diagnostic logs)."""

from __future__ import annotations

from typing import Any


class AuditMixin:
    def list_audit_events(self, **params: Any) -> list[dict]:
        """Optional filters: ``event``, ``timefrom``, ``timeto``, ``sortby``, ``filter``."""
        return list(self.paginate("/audit/events", params=params))

    def get_audit_event(self, event_id: str) -> dict:
        return self.get(f"/audit/events/{event_id}")

    def export_audit_events(self, **params: Any) -> Any:
        """Optional filters as in ``list_audit_events``, plus ``format``."""
        return self.get("/audit/export", params=params)

    def list_logs(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/logs/{org_id}"))
