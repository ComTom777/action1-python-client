"""``/scripts/all`` (custom scripts)."""

from __future__ import annotations

from typing import Any


class ScriptsMixin:
    def list_scripts(self) -> list[dict]:
        return list(self.paginate("/scripts/all"))

    def get_script(self, script_id: str) -> dict:
        return self.get(f"/scripts/all/{script_id}")

    def create_script(self, **fields: Any) -> dict:
        return self.post("/scripts/all", json=fields)

    def update_script(self, script_id: str, **fields: Any) -> dict:
        return self.patch(f"/scripts/all/{script_id}", json=fields)

    def delete_script(self, script_id: str) -> None:
        self.delete(f"/scripts/all/{script_id}")
