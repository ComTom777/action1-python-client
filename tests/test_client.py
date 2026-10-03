import httpx
import pytest
import respx

from action1_client import Action1APIError, Action1AuthError, Action1Client

BASE = "https://app.eu.action1.com/api/3.0"


def make_client() -> Action1Client:
    return Action1Client("api-key-test@action1.com", "secret", region="europe")


@respx.mock
def test_auth_then_get_sends_bearer_token():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123", "expires_in": 3600})
    )
    org_route = respx.get(f"{BASE}/organizations/org-1").mock(
        return_value=httpx.Response(200, json={"id": "org-1", "name": "Acme"})
    )

    with make_client() as client:
        org = client.get_organization("org-1")

    assert org == {"id": "org-1", "name": "Acme"}
    sent_request = org_route.calls[0].request
    assert sent_request.headers["Authorization"] == "Bearer tok-123"


@respx.mock
def test_token_is_cached_across_calls():
    token_route = respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123", "expires_in": 3600})
    )
    respx.get(f"{BASE}/organizations/org-1").mock(
        return_value=httpx.Response(200, json={"id": "org-1"})
    )

    with make_client() as client:
        client.get_organization("org-1")
        client.get_organization("org-1")

    assert token_route.call_count == 1


@respx.mock
def test_auth_failure_raises_action1_auth_error():
    respx.post(f"{BASE}/oauth2/token").mock(return_value=httpx.Response(401, text="bad creds"))

    with make_client() as client:
        with pytest.raises(Action1AuthError):
            client.get_organization("org-1")


@respx.mock
def test_api_error_uses_user_message_from_body():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123", "expires_in": 3600})
    )
    respx.get(f"{BASE}/organizations/missing").mock(
        return_value=httpx.Response(
            400,
            json={
                "status": 400,
                "developer_message": "Organization with id=missing not found",
                "user_message": "Organization with id=missing not found",
            },
        )
    )

    with make_client() as client:
        with pytest.raises(Action1APIError) as exc_info:
            client.get_organization("missing")

    assert "Organization with id=missing not found" in str(exc_info.value)
    assert exc_info.value.status_code == 400


@respx.mock
def test_paginate_follows_next_page_until_exhausted():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123", "expires_in": 3600})
    )
    respx.get(f"{BASE}/organizations", params={"limit": "50", "from": "0"}).mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": "1"}, {"id": "2"}], "next_page": "?from=2"},
        )
    )
    respx.get(f"{BASE}/organizations", params={"limit": "50", "from": "2"}).mock(
        return_value=httpx.Response(200, json={"items": [{"id": "3"}], "next_page": ""})
    )

    with make_client() as client:
        orgs = client.list_organizations()

    assert [o["id"] for o in orgs] == ["1", "2", "3"]


@respx.mock
def test_add_endpoint_group_members_builds_batch_body():
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123", "expires_in": 3600})
    )
    route = respx.post(f"{BASE}/endpoints/groups/org-1/group-1/contents").mock(
        return_value=httpx.Response(200, json={"result": "ok"})
    )

    with make_client() as client:
        client.add_endpoint_group_members("org-1", "group-1", ["ep-1", "ep-2"])

    sent_body = route.calls[0].request.content
    import json

    assert json.loads(sent_body) == [
        {"method": "POST", "data": {"endpoint_id": "ep-1", "type": "Endpoint"}},
        {"method": "POST", "data": {"endpoint_id": "ep-2", "type": "Endpoint"}},
    ]


@respx.mock
def test_paginate_uses_total_items_when_next_page_missing():
    # /vulnerabilities returns total_items but never next_page - live tenant had 3104 CVEs and
    # we were returning only the first 50.
    respx.post(f"{BASE}/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123", "expires_in": 3600})
    )
    respx.get(f"{BASE}/organizations", params={"limit": "50", "from": "0"}).mock(
        return_value=httpx.Response(200, json={"items": [{"id": "1"}, {"id": "2"}], "total_items": 3})
    )
    respx.get(f"{BASE}/organizations", params={"limit": "50", "from": "2"}).mock(
        return_value=httpx.Response(200, json={"items": [{"id": "3"}], "total_items": "3"})
    )

    with make_client() as client:
        assert [o["id"] for o in client.list_organizations()] == ["1", "2", "3"]
