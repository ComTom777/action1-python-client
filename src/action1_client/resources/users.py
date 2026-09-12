"""``/users``."""

from __future__ import annotations

from typing import Any


class UsersMixin:
    def list_users(self) -> list[dict]:
        return list(self.paginate("/users"))

    def get_user(self, user_id: str) -> dict:
        return self.get(f"/users/{user_id}")

    def create_user(self, **fields: Any) -> dict:
        return self.post("/users", json=fields)

    def update_user(self, user_id: str, **fields: Any) -> dict:
        return self.patch(f"/users/{user_id}", json=fields)

    def delete_user(self, user_id: str) -> None:
        self.delete(f"/users/{user_id}")

    def list_user_roles(self, user_id: str) -> list[dict]:
        return list(self.paginate(f"/users/{user_id}/roles"))
