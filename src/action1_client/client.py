"""``Action1Client``: composes the HTTP/auth base with one mixin per API resource group.

Endpoint paths and the OAuth2 client-credentials flow were verified against a live tenant and
against Action1's real OpenAPI spec (extracted from the Swagger UI bundle - it isn't published
as a standalone file). ``coverage_check.py`` in the repo root diffs this client's methods against
that spec; run it after adding new endpoints.
"""

from __future__ import annotations

from ._http import REGION_HOSTS, Action1HTTPBase
from .resources import (
    AuditMixin,
    AutomationsMixin,
    DataSourcesMixin,
    EndpointGroupsMixin,
    EndpointsMixin,
    EnterpriseMixin,
    InstalledSoftwareMixin,
    MeMixin,
    OrganizationsMixin,
    PackagesMixin,
    ReportsMixin,
    RolesMixin,
    ScriptsMixin,
    SettingsMixin,
    UpdatesMixin,
    UsersMixin,
    VulnerabilitiesMixin,
)

__all__ = ["Action1Client", "REGION_HOSTS"]


class Action1Client(
    MeMixin,
    OrganizationsMixin,
    EndpointsMixin,
    EndpointGroupsMixin,
    VulnerabilitiesMixin,
    AutomationsMixin,
    ScriptsMixin,
    PackagesMixin,
    UpdatesMixin,
    InstalledSoftwareMixin,
    DataSourcesMixin,
    SettingsMixin,
    ReportsMixin,
    RolesMixin,
    UsersMixin,
    EnterpriseMixin,
    AuditMixin,
    Action1HTTPBase,
):
    """A connection to one Action1 tenant, scoped to one region.

    Usage::

        with Action1Client(client_id, client_secret, region="europe") as client:
            for org in client.list_organizations():
                print(org["name"])
    """
