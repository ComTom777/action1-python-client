"""``/automations/schedules``, ``/automations/instances``, and action templates.

Note: Action1's API has no endpoint to trigger an existing schedule on demand, and no clone
endpoint for automations - see ``create_automation_instance`` for the actual "run this now"
mechanism (submitting a full instance definition), and don't add a ``clone_automation`` here
without checking the spec again first, since it was previously fabricated in PSAction1.
"""

from __future__ import annotations

from typing import Any


class AutomationsMixin:
    # -- Schedules (recurring automation definitions) --

    def list_automation_schedules(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/automations/schedules/{org_id}"))

    def get_automation_schedule(self, org_id: str, automation_id: str) -> dict:
        return self.get(f"/automations/schedules/{org_id}/{automation_id}")

    def create_automation_schedule(self, org_id: str, **fields: Any) -> dict:
        """``fields`` typically includes ``name``, ``retry_minutes``, ``actions``, ``endpoints``."""
        return self.post(f"/automations/schedules/{org_id}", json=fields)

    def update_automation_schedule(self, org_id: str, automation_id: str, **fields: Any) -> dict:
        return self.patch(f"/automations/schedules/{org_id}/{automation_id}", json=fields)

    def delete_automation_schedule(self, org_id: str, automation_id: str) -> None:
        self.delete(f"/automations/schedules/{org_id}/{automation_id}")

    def delete_automation_action(self, org_id: str, automation_id: str, action_id: str) -> dict:
        return self.delete(f"/automations/schedules/{org_id}/{automation_id}/actions/{action_id}")

    def get_automation_deployment_statuses(self, org_id: str, automation_id: str) -> list[dict]:
        return list(
            self.paginate(f"/automations/schedules/{org_id}/{automation_id}/deployment-statuses")
        )

    # -- Instances (one-off / in-progress runs) --

    def list_automation_instances(self, org_id: str) -> list[dict]:
        return list(self.paginate(f"/automations/instances/{org_id}"))

    def get_automation_instance(self, org_id: str, instance_id: str) -> dict:
        return self.get(f"/automations/instances/{org_id}/{instance_id}")

    def create_automation_instance(self, org_id: str, **fields: Any) -> dict:
        """Applies/executes an automation now. ``fields``: ``name``, ``actions``, ``endpoints``."""
        return self.post(f"/automations/instances/{org_id}", json=fields)

    def run_script(
        self, org_id: str, endpoint_ids: list[str], script_text: str, *, name: str = "Run PowerShell script"
    ) -> dict:
        """Run an inline PowerShell script now (as SYSTEM) on the given endpoints; returns the
        automation instance. Each endpoint's output (stdout, capped at ~10,000 chars by Action1)
        shows up as ``description`` in ``list_automation_instance_endpoint_results``.

        ``retry_minutes`` is required though the spec doesn't say so; the reboot settings are
        spelled out because the spec's own example auto-reboots on exit code 365.
        """
        return self.create_automation_instance(
            org_id,
            name=name,
            retry_minutes="60",
            endpoints=[{"id": e, "type": "Endpoint"} for e in endpoint_ids],
            actions=[{
                "name": "Run PowerShell",
                "template_id": "run_script",
                "params": {
                    "display_summary": "",
                    "condition_script_text": "",
                    "condition_script_language": "PowerShell",
                    "run_script_params": [],
                    "run_script_text": script_text,
                    "run_script_language": "PowerShell",
                    "reboot_exit_codes": "",
                    "reboot_options": {"auto_reboot": "no"},
                },
            }],
        )

    def list_automation_instance_endpoint_results(self, org_id: str, instance_id: str) -> list[dict]:
        return list(
            self.paginate(f"/automations/instances/{org_id}/{instance_id}/endpoint-results")
        )

    def get_automation_instance_endpoint_details(
        self, org_id: str, instance_id: str, endpoint_id: str
    ) -> list[dict]:
        return list(
            self.paginate(
                f"/automations/instances/{org_id}/{instance_id}/endpoint-results/{endpoint_id}/details"
            )
        )

    def stop_automation_instance(self, org_id: str, instance_id: str) -> Any:
        return self.post(f"/automations/instances/{org_id}/{instance_id}/stop")

    # -- Action templates (building blocks referenced by schedules/instances) --

    def list_action_templates(self) -> list[dict]:
        return list(self.paginate("/automations/action-templates"))

    def get_action_template(self, template_id: str) -> dict:
        return self.get(f"/automations/action-templates/{template_id}")
