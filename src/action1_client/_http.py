"""Auth + generic request/pagination plumbing, shared by every resource mixin."""

from __future__ import annotations

import time
from typing import Any, Iterator

import httpx

from .exceptions import Action1APIError, Action1AuthError

REGION_HOSTS = {
    "north_america": "https://app.action1.com/api/3.0",
    "europe": "https://app.eu.action1.com/api/3.0",
    "australia": "https://app.au.action1.com/api/3.0",
}


class Action1HTTPBase:
    """OAuth2 client-credentials auth + thin GET/POST/PATCH/PUT/DELETE wrappers."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        region: str = "north_america",
        timeout: float = 30.0,
    ):
        if region not in REGION_HOSTS:
            valid = ", ".join(sorted(REGION_HOSTS))
            raise ValueError(f"Unknown region {region!r}. Valid regions: {valid}")

        self._client_id = client_id
        self._client_secret = client_secret
        self._http = httpx.Client(base_url=REGION_HOSTS[region], timeout=timeout)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Action1HTTPBase":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _ensure_token(self) -> None:
        if self._access_token and time.monotonic() < self._token_expires_at:
            return

        response = self._http.post(
            "/oauth2/token",
            data={"client_id": self._client_id, "client_secret": self._client_secret},
        )
        if response.status_code != 200:
            raise Action1AuthError(
                f"Authentication failed ({response.status_code}): {response.text}"
            )

        payload = response.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        # Refresh a few seconds early so a request doesn't race an about-to-expire token.
        self._token_expires_at = time.monotonic() + expires_in - 5

    def _auth_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        self._ensure_token()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        if extra:
            headers.update(extra)
        return headers

    # ------------------------------------------------------------------
    # Generic request plumbing
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        response = self._http.request(
            method,
            path,
            params=params,
            json=json,
            content=content,
            headers=self._auth_headers(headers),
        )
        if response.status_code >= 400:
            raise Action1APIError.from_response(response)
        return response

    def _json_or_none(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        return response.json()

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._json_or_none(self._request("GET", path, params=params))

    def post(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
        return self._json_or_none(self._request("POST", path, params=params, json=json))

    def patch(self, path: str, *, json: Any = None) -> Any:
        return self._json_or_none(self._request("PATCH", path, json=json))

    def put(
        self,
        path: str,
        *,
        content: bytes | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._json_or_none(
            self._request("PUT", path, params=params, content=content, headers=headers)
        )

    def delete(self, path: str) -> Any:
        return self._json_or_none(self._request("DELETE", path))

    def paginate(self, path: str, *, params: dict[str, Any] | None = None) -> Iterator[dict]:
        """Yield every item across all pages of a ResultPage-shaped GET endpoint."""
        params = dict(params or {})
        params.setdefault("limit", 50)
        params.setdefault("from", 0)

        while True:
            page = self.get(path, params=params)
            items = page.get("items", []) if isinstance(page, dict) else []
            yield from items
            if not items or not page.get("next_page"):
                break
            params["from"] = params["from"] + len(items)
