from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_SECONDS
from .protocol import HaierClient, HaierError, HaierState

_LOGGER = logging.getLogger(__name__)


class HaierLocalCoordinator(DataUpdateCoordinator[HaierState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: HaierClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> HaierState:
        try:
            return await self.client.read_state()
        except HaierError as err:
            raise UpdateFailed(str(err)) from err

    async def async_set(self, **change) -> None:
        try:
            state = await self.client.set_state(**change)
        except HaierError as err:
            raise UpdateFailed(str(err)) from err
        self.async_set_updated_data(state)
