"""``/endpoints/managed``, agent installation/deployment, and remote sessions."""

from __future__ import annotations

from typing import Any


class EndpointsMixin:
    def list_endpoints(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/endpoints/managed/{org_id}"))

    def get_endpoint(self, org_id: str, endpoint_id: str) -> dict:
        return self.get(f"/endpoints/managed/{org_id}/{endpoint_id}")

    def update_endpoint(self, org_id: str, endpoint_id: str, **fields: Any) -> dict:
        return self.patch(f"/endpoints/managed/{org_id}/{endpoint_id}", json=fields)

    def delete_endpoint(self, org_id: str, endpoint_id: str) -> None:
        self.delete(f"/endpoints/managed/{org_id}/{endpoint_id}")

    def move_endpoint(self, org_id: str, endpoint_id: str, group_id: str) -> dict:
        return self.post(
            f"/endpoints/managed/{org_id}/{endpoint_id}/move",
            json={"group_id": group_id},
        )

    def get_endpoint_status(self, org_id: str) -> dict:
        """Aggregate connected/disconnected/pending counts for the organization."""
        return self.get(f"/endpoints/status/{org_id}")

    def get_endpoint_missing_updates(self, org_id: str, endpoint_id: str) -> list[dict]:
        return list(self.paginate(f"/endpoints/managed/{org_id}/{endpoint_id}/missing-updates"))

    def get_agent_installation_url(self, org_id: str, install_type: str) -> dict:
        """``install_type`` e.g. ``windowsEXE``, ``windowsMSI``, ``macOSPKG``, ``linuxDEB``."""
        return self.get(f"/endpoints/agent-installation/{org_id}/{install_type}")

    def get_agent_deployment_settings(self, org_id: str) -> dict:
        return self.get(f"/endpoints/agent-deployment/{org_id}")

    def update_agent_deployment_settings(self, org_id: str, **fields: Any) -> dict:
        return self.patch(f"/endpoints/agent-deployment/{org_id}", json=fields)

    # -- Remote sessions --

    def start_remote_session(
        self, org_id: str, endpoint_id: str, *, current_ip: str | None = None
    ) -> dict:
        body: dict[str, Any] = {"connection_type": "assistance"}
        if current_ip:
            body["current_ip"] = current_ip
        return self.post(f"/endpoints/managed/{org_id}/{endpoint_id}/remote-sessions", json=body)

    def get_remote_session(self, org_id: str, endpoint_id: str, session_id: str) -> dict:
        return self.get(
            f"/endpoints/managed/{org_id}/{endpoint_id}/remote-sessions/{session_id}"
        )

    def switch_remote_session_monitor(
        self, org_id: str, endpoint_id: str, session_id: str, current_monitor: int
    ) -> dict:
        return self.patch(
            f"/endpoints/managed/{org_id}/{endpoint_id}/remote-sessions/{session_id}",
            json={"current_monitor": current_monitor},
        )

    # -- Deployers (agentless discovery/deployment appliances) --

    def list_deployers(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/endpoints/deployers/{org_id}"))

    def get_deployer(self, org_id: str, deployer_id: str) -> dict:
        return self.get(f"/endpoints/deployers/{org_id}/{deployer_id}")

    def delete_deployer(self, org_id: str, deployer_id: str) -> None:
        self.delete(f"/endpoints/deployers/{org_id}/{deployer_id}")

    def get_deployer_installation_url(self, org_id: str) -> dict:
        return self.get(f"/endpoints/deployer-installation/{org_id}/windowsEXE")
