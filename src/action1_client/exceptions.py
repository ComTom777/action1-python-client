"""Exceptions raised by the Action1 client."""

from __future__ import annotations

import httpx


class Action1Error(Exception):
    """Base class for all errors raised by this library."""


class Action1AuthError(Action1Error):
    """Raised when the OAuth2 client-credentials exchange fails."""


class Action1APIError(Action1Error):
    """Raised when the Action1 API returns an HTTP error status.

    Action1's error body is ``{"status": ..., "developer_message": ..., "user_message": ...}``;
    ``message`` prefers ``user_message`` since it's meant to be human-readable.
    """

    def __init__(self, status_code: int, message: str, *, response: httpx.Response | None = None):
        self.status_code = status_code
        self.response = response
        super().__init__(f"Action1 API error {status_code}: {message}")

    @classmethod
    def from_response(cls, response: httpx.Response) -> "Action1APIError":
        message = response.text
        try:
            body = response.json()
            message = body.get("user_message") or body.get("developer_message") or message
        except ValueError:
            pass
        return cls(response.status_code, message, response=response)
