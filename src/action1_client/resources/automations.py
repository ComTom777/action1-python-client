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
