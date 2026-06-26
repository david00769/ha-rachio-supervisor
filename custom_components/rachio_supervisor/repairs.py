"""Repairs for Rachio Supervisor."""

from __future__ import annotations

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WEBHOOK_REPAIR_ISSUE_PREFIX, RachioSupervisorCoordinator


class WebhookRegistrationRepairFlow(RepairsFlow):
    """Verify the linked Rachio webhook registration after operator repair."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> RepairsFlowResult:
        """Start the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self,
        user_input: dict[str, str] | None = None,
    ) -> RepairsFlowResult:
        """Refresh live Rachio evidence and close only after the webhook is valid."""
        coordinator = _loaded_coordinator(self.hass, self._entry_id)
        if coordinator is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={},
                errors={"base": "entry_not_loaded"},
            )

        if user_input is not None:
            coordinator.force_next_reconciliation()
            await coordinator.async_request_refresh()
            evidence = coordinator._cached_evidence
            if evidence is not None and evidence.webhook_health == "registered":
                coordinator.clear_webhook_repair_issue()
                return self.async_create_entry(title="", data={})
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=_description_placeholders(coordinator),
                errors={"base": "webhook_still_unhealthy"},
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=_description_placeholders(coordinator),
        )


def _loaded_coordinator(
    hass: HomeAssistant,
    entry_id: str,
) -> RachioSupervisorCoordinator | None:
    coordinators = hass.data.get(DOMAIN, {})
    coordinator = coordinators.get(entry_id)
    if isinstance(coordinator, RachioSupervisorCoordinator):
        return coordinator
    return None


def _description_placeholders(
    coordinator: RachioSupervisorCoordinator,
) -> dict[str, str]:
    data = coordinator.data
    return {
        "site_name": data.site_name,
        "linked_entry_title": data.linked_entry_title,
        "webhook_health": data.webhook_health,
        "webhook_count": str(data.webhook_count),
        "webhook_url": data.webhook_url or "none",
        "webhook_external_id": data.webhook_external_id or "none",
    }


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for a repair issue."""
    if issue_id.startswith(WEBHOOK_REPAIR_ISSUE_PREFIX) and data:
        entry_id = data.get("entry_id")
        if isinstance(entry_id, str):
            return WebhookRegistrationRepairFlow(entry_id)
    raise ValueError(f"unknown repair {issue_id}")  # pragma: no cover
