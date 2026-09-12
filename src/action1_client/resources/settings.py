"""``/settings/all`` and ``/setting-templates/all``."""

from __future__ import annotations

from typing import Any


class SettingsMixin:
    def list_settings(self) -> list[dict]:
        return list(self.paginate("/settings/all"))

    def get_setting(self, setting_id: str) -> dict:
        return self.get(f"/settings/all/{setting_id}")

    def create_setting(self, **fields: Any) -> dict:
        return self.post("/settings/all", json=fields)

    def update_setting(self, setting_id: str, **fields: Any) -> dict:
        return self.patch(f"/settings/all/{setting_id}", json=fields)

    def delete_setting(self, setting_id: str) -> None:
        self.delete(f"/settings/all/{setting_id}")

    def list_setting_templates(self) -> list[dict]:
        return list(self.paginate("/setting-templates/all"))

    def get_setting_template(self, template_id: str) -> dict:
        return self.get(f"/setting-templates/all/{template_id}")
