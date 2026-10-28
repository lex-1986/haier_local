from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_HOST, CONF_MAC, CONF_NAME, DOMAIN
from .protocol import HaierClient, HaierError, normalise_mac

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Haier"): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_MAC): str,
    }
)


class HaierLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mac = normalise_mac(user_input[CONF_MAC])
            except ValueError:
                errors[CONF_MAC] = "invalid_mac"
            else:
                try:
                    await HaierClient(user_input[CONF_HOST], mac).read_state()
                except HaierError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(format_mac(mac))
                    self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})
                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data={**user_input, CONF_MAC: mac}
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_DATA_SCHEMA, user_input),
            errors=errors,
        )
