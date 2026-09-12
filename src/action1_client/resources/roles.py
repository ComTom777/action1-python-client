"""``/roles`` (RBAC) and ``/permissions``."""

from __future__ import annotations

from typing import Any


class RolesMixin:
    def list_roles(self) -> list[dict]:
        return list(self.paginate("/roles"))

    def get_role(self, role_id: str) -> dict:
        return self.get(f"/roles/{role_id}")

    def create_role(self, **fields: Any) -> dict:
        return self.post("/roles", json=fields)

    def update_role(self, role_id: str, **fields: Any) -> dict:
        return self.patch(f"/roles/{role_id}", json=fields)

    def delete_role(self, role_id: str) -> None:
        self.delete(f"/roles/{role_id}")

    def clone_role(self, role_id: str, **fields: Any) -> dict:
        return self.post(f"/roles/{role_id}/clone", json=fields)

    def list_role_users(self, role_id: str) -> list[dict]:
        return list(self.paginate(f"/roles/{role_id}/users"))

    def assign_role_to_user(self, role_id: str, user_id: str) -> Any:
        return self.post(f"/roles/{role_id}/users/{user_id}")

    def unassign_role_from_user(self, role_id: str, user_id: str) -> None:
        self.delete(f"/roles/{role_id}/users/{user_id}")

    def list_permissions(self) -> list[dict]:
        return list(self.paginate("/permissions"))
