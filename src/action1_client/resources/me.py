"""``/me`` and ``/me/report-subscriptions``."""

from __future__ import annotations

from typing import Any


class MeMixin:
    def me(self) -> dict:
        return self.get("/me")

    def update_me(self, **fields: Any) -> dict:
        return self.patch("/me", json=fields)

    def list_report_subscriptions(self) -> list[dict]:
        return list(self.paginate("/me/report-subscriptions"))

    def create_report_subscription(self, **fields: Any) -> dict:
        return self.post("/me/report-subscriptions", json=fields)

    def update_report_subscription(self, subscription_id: str, **fields: Any) -> dict:
        return self.patch(f"/me/report-subscriptions/{subscription_id}", json=fields)

    def delete_report_subscription(self, subscription_id: str) -> None:
        self.delete(f"/me/report-subscriptions/{subscription_id}")
