"""Auth + generic request/pagination plumbing, shared by every resource mixin."""

from __future__ import annotations

import time
from typing import Any, Iterator
from urllib.parse import unquote

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

        try:
            payload = response.json()
            access_token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 3600))
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("access_token is missing or not a non-empty string")
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            raise Action1AuthError(
                f"Authentication succeeded but the token response was malformed: {response.text}"
            ) from exc

        self._access_token = access_token
        # Refresh a few seconds early so a request doesn't race an about-to-expire token
        # (floored at 0 so a short-lived token doesn't push the expiry into the past, which
        # would force a re-auth round trip on every single request).
        self._token_expires_at = time.monotonic() + max(expires_in - 5, 0)

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
        # ``path`` is built by interpolating resource IDs (e.g. ``f"/organizations/{org_id}"``)
        # that may come from untrusted callers (an MCP server forwarding tool-call arguments,
        # say). httpx treats an absolute URL as an override of base_url - not a relative path
        # under it - which would leak the bearer token to an arbitrary host; and a ".." path
        # segment (including percent-encoded, hence the unquote()) can walk the request outside
        # the versioned API path (verified: "/organizations/../../oauth2/token" resolves to
        # ".../api/oauth2/token"). Both are rejected here, the one place every request passes
        # through. Segment-exact matching (not a bare substring check) so a legitimate ID like
        # "release..1" isn't falsely rejected.
        decoded = unquote(path)
        if "://" in decoded or decoded.startswith("//"):
            raise ValueError(f"path must be a relative API path, got {path!r}")
        if ".." in decoded.split("/"):
            raise ValueError(f"path must not contain a '..' segment: {path!r}")
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
        params["from"] = int(params.setdefault("from", 0))

        while True:
            page = self.get(path, params=params)
            items = page.get("items", []) if isinstance(page, dict) else []
            yield from items
            params["from"] += len(items)
            # Some endpoints (e.g. /vulnerabilities) send total_items but no next_page.
            # (total_items arrives as an int on some endpoints, a string on others.)
            more = page.get("next_page") or params["from"] < int(page.get("total_items") or 0)
            if not items or not more:
                break
