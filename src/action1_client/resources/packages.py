"""``/software-repository`` (packages, versions, and the chunked binary upload protocol).

The upload flow is Action1's take on a resumable-upload protocol, not a simple multipart POST:

1. POST .../upload with ``X-Upload-Content-Type``/``X-Upload-Content-Length`` headers and a
   ``platform`` query param. Action1 replies **308** (not 200) with an ``X-Upload-Location``
   header that embeds an ``upload_id``.
2. PUT .../upload?platform=...&upload_id=... once per chunk, each with a ``Content-Range``
   header (``bytes start-end/total``) and the raw chunk bytes as the body.

``upload_package_version`` does both steps for you.
"""

from __future__ import annotations

import mimetypes
import os
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..exceptions import Action1Error


class PackagesMixin:
    def list_packages(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/software-repository/{org_id}"))

    def get_package(self, org_id: str, package_id: str) -> dict:
        return self.get(f"/software-repository/{org_id}/{package_id}")

    def create_package(self, org_id: str, **fields: Any) -> dict:
        return self.post(f"/software-repository/{org_id}", json=fields)

    def update_package(self, org_id: str, package_id: str, **fields: Any) -> dict:
        return self.patch(f"/software-repository/{org_id}/{package_id}", json=fields)

    def delete_package(self, org_id: str, package_id: str) -> None:
        self.delete(f"/software-repository/{org_id}/{package_id}")

    def clone_package(self, org_id: str, package_id: str, **fields: Any) -> dict:
        return self.post(f"/software-repository/{org_id}/{package_id}/clone", json=fields)

    def get_package_match_conflicts(self, org_id: str, app_name_match: str) -> Any:
        """``app_name_match``: the spec marks this optional but the live API 400s without it."""
        return self.get(
            f"/software-repository/{org_id}/match-conflicts",
            params={"app_name_match": app_name_match},
        )

    def get_package_version_match_conflicts(
        self, org_id: str, package_id: str, app_name_match: str
    ) -> Any:
        return self.get(
            f"/software-repository/{org_id}/{package_id}/match-conflicts",
            params={"app_name_match": app_name_match},
        )

    # -- Versions --

    def create_package_version(self, org_id: str, package_id: str, **fields: Any) -> dict:
        return self.post(f"/software-repository/{org_id}/{package_id}/versions", json=fields)

    def get_package_version(self, org_id: str, package_id: str, version_id: str) -> dict:
        return self.get(f"/software-repository/{org_id}/{package_id}/versions/{version_id}")

    def update_package_version(
        self, org_id: str, package_id: str, version_id: str, **fields: Any
    ) -> dict:
        return self.patch(
            f"/software-repository/{org_id}/{package_id}/versions/{version_id}", json=fields
        )

    def delete_package_version(self, org_id: str, package_id: str, version_id: str) -> None:
        self.delete(f"/software-repository/{org_id}/{package_id}/versions/{version_id}")

    def delete_package_version_action(
        self, org_id: str, package_id: str, version_id: str, action_id: str
    ) -> None:
        self.delete(
            f"/software-repository/{org_id}/{package_id}/versions/{version_id}"
            f"/additional-actions/{action_id}"
        )

    # -- Binary upload (resumable-upload protocol) --

    def _initiate_package_upload(
        self,
        org_id: str,
        package_id: str,
        version_id: str,
        *,
        platform: str,
        content_type: str,
        content_length: int,
    ) -> str:
        path = f"/software-repository/{org_id}/{package_id}/versions/{version_id}/upload"
        response = self._request(
            "POST",
            path,
            params={"platform": platform},
            headers={
                "X-Upload-Content-Type": content_type,
                "X-Upload-Content-Length": str(content_length),
            },
        )
        location = response.headers.get("X-Upload-Location") or response.headers.get("Location")
        if not location:
            raise Action1Error(
                "Upload initialization response did not include an X-Upload-Location header"
            )
        upload_id = parse_qs(urlparse(location).query).get("upload_id", [None])[0]
        if not upload_id:
            raise Action1Error(f"Could not parse upload_id from response header: {location!r}")
        return upload_id

    def upload_package_version(
        self,
        org_id: str,
        package_id: str,
        version_id: str,
        file_path: str,
        *,
        platform: str,
        chunk_size: int = 8 * 1024 * 1024,
        content_type: str | None = None,
    ) -> dict:
        """Uploads a local file as a package version's binary.

        ``platform`` is ``Windows_32`` or ``Windows_64`` (per PSAction1's ``-Platform``
        ValidateSet; the spec itself only documents it as a free-text query param).
        """
        size = os.path.getsize(file_path)
        resolved_content_type = content_type or mimetypes.guess_type(file_path)[0] or (
            "application/octet-stream"
        )
        upload_id = self._initiate_package_upload(
            org_id,
            package_id,
            version_id,
            platform=platform,
            content_type=resolved_content_type,
            content_length=size,
        )

        path = f"/software-repository/{org_id}/{package_id}/versions/{version_id}/upload"
        with open(file_path, "rb") as file_obj:
            offset = 0
            while offset < size:
                chunk = file_obj.read(chunk_size)
                if not chunk:
                    break
                end = offset + len(chunk) - 1
                self.put(
                    path,
                    content=chunk,
                    params={"platform": platform, "upload_id": upload_id},
                    headers={
                        "Content-Range": f"bytes {offset}-{end}/{size}",
                        "Content-Length": str(len(chunk)),
                    },
                )
                offset += len(chunk)

        return {"upload_id": upload_id, "bytes_uploaded": size}
