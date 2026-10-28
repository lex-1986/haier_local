from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_MAC
from .coordinator import HaierLocalCoordinator
from .protocol import HaierClient

PLATFORMS = [Platform.CLIMATE]

type HaierLocalConfigEntry = ConfigEntry[HaierLocalCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HaierLocalConfigEntry) -> bool:
    client = HaierClient(entry.data[CONF_HOST], entry.data[CONF_MAC])
    coordinator = HaierLocalCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HaierLocalConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
