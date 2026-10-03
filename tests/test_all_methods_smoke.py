"""Calls every public resource method with dummy arguments against a mocked API.

This is a regression net, not a correctness check: it doesn't verify *which* URL each method
hits (test_client.py does that for the interesting cases), it verifies that every method builds
a request that doesn't blow up - wrong parameter name, wrong f-string variable, wrong HTTP verb
signature, etc. New resource methods are picked up automatically via ``inspect``, so this stays
in sync with the client without hand-maintaining a list of ~140 cases.
"""

from __future__ import annotations

import inspect
import os
import tempfile

import httpx
import pytest
import respx

from action1_client import Action1Client
from action1_client._http import Action1HTTPBase

BASE = "https://app.action1.com/api/3.0"

# Names defined directly on the HTTP base class - generic plumbing, not resource endpoints.
_BASE_METHOD_NAMES = set(vars(Action1HTTPBase).keys())

# These need bespoke setup (a real file on disk, a 308 response with a special header) and get
# their own dedicated tests below instead of the generic loop.
_SKIP_IN_GENERIC_LOOP = {"upload_package_version"}


def _dummy_value(param: inspect.Parameter):
    name = param.name
    annotation = str(param.annotation)
    if name == "endpoint_ids" or "Iterable" in annotation or "list" in annotation.lower():
        return ["dummy-1", "dummy-2"]
    if annotation == "dict":
        return {"id": "dummy-id", "self": "dummy-self"}
    if "int" in annotation:
        return 1
    return f"dummy-{name}"


def _public_resource_methods(client: Action1Client):
    for name, member in inspect.getmembers(type(client), predicate=inspect.isfunction):
        if name.startswith("_") or name in _BASE_METHOD_NAMES or name in _SKIP_IN_GENERIC_LOOP:
            continue
        yield name, member


@respx.mock
def test_every_public_method_builds_a_valid_request():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )
    # Catch-all: anything not more specifically matched above gets a generic ResultPage-shaped
    # body (works for both list-returning and single-object-returning methods, since callers
    # either read .get("items") via paginate() or use the dict directly).
    respx.route().mock(
        return_value=httpx.Response(200, json={"id": "x", "items": [{"id": "x"}], "next_page": ""})
    )

    client = Action1Client("dummy-client-id", "dummy-secret", region="north_america")
    failures: list[tuple[str, str]] = []

    for name, func in _public_resource_methods(client):
        sig = inspect.signature(func)
        args = [
            _dummy_value(p)
            for pname, p in sig.parameters.items()
            if pname != "self"
            and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            and p.default is inspect.Parameter.empty
        ]
        try:
            getattr(client, name)(*args)
        except Exception as exc:  # noqa: BLE001 - we want to collect every failure, not stop at the first
            failures.append((name, repr(exc)))

    assert not failures, "\n".join(f"{name}: {err}" for name, err in failures)


@respx.mock
def test_upload_package_version_full_chunked_flow():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )
    init_route = respx.post(
        f"{BASE}/software-repository/org-1/pkg-1/versions/ver-1/upload"
    ).mock(
        return_value=httpx.Response(
            308,
            headers={
                "X-Upload-Location": (
                    "/software-repository/org-1/pkg-1/versions/ver-1/upload"
                    "?platform=Windows_64&upload_id=session-abc"
                )
            },
        )
    )
    chunk_route = respx.put(
        f"{BASE}/software-repository/org-1/pkg-1/versions/ver-1/upload"
    ).mock(return_value=httpx.Response(200))

    with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as f:
        f.write(b"x" * 1000)
        file_path = f.name

    try:
        client = Action1Client("id", "secret")
        result = client.upload_package_version(
            "org-1", "pkg-1", "ver-1", file_path, platform="Windows_64", chunk_size=400
        )
    finally:
        os.unlink(file_path)

    assert result == {"upload_id": "session-abc", "bytes_uploaded": 1000}
    assert init_route.called
    assert chunk_route.call_count == 3  # 400 + 400 + 200 bytes

    first_chunk_headers = chunk_route.calls[0].request.headers
    assert first_chunk_headers["Content-Range"] == "bytes 0-399/1000"
    last_chunk_headers = chunk_route.calls[-1].request.headers
    assert last_chunk_headers["Content-Range"] == "bytes 800-999/1000"


@respx.mock
def test_upload_package_version_raises_if_location_header_missing():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )
    respx.post(f"{BASE}/software-repository/org-1/pkg-1/versions/ver-1/upload").mock(
        return_value=httpx.Response(308)
    )

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"x")
        file_path = f.name

    try:
        client = Action1Client("id", "secret")
        with pytest.raises(Exception, match="X-Upload-Location"):
            client.upload_package_version("org-1", "pkg-1", "ver-1", file_path, platform="Windows_64")
    finally:
        os.unlink(file_path)
