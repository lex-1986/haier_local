from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HaierLocalConfigEntry
from .const import CONF_MAC, DOMAIN
from .coordinator import HaierLocalCoordinator
from .protocol import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MID,
    MODE_AUTO,
    MODE_COOL,
    MODE_DRY,
    MODE_FAN,
    MODE_HEAT,
)

HVAC_FROM_MODE = {
    MODE_AUTO: HVACMode.AUTO,
    MODE_COOL: HVACMode.COOL,
    MODE_HEAT: HVACMode.HEAT,
    MODE_FAN: HVACMode.FAN_ONLY,
    MODE_DRY: HVACMode.DRY,
}
MODE_FROM_HVAC = {v: k for k, v in HVAC_FROM_MODE.items()}

FAN_FROM_RAW = {FAN_AUTO: "auto", FAN_LOW: "low", FAN_MID: "medium", FAN_HIGH: "high"}
RAW_FROM_FAN = {v: k for k, v in FAN_FROM_RAW.items()}
FAN_QUIET = "quiet"
FAN_TURBO = "turbo"

SWING_ON = "on"
SWING_OFF = "off"


async def async_setup_entry(
    hass: HomeAssistant, entry: HaierLocalConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([HaierLocalClimate(entry.runtime_data, entry)])


class HaierLocalClimate(CoordinatorEntity[HaierLocalCoordinator], ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.OFF, *HVAC_FROM_MODE.values()]
    _attr_fan_modes = [*RAW_FROM_FAN, FAN_QUIET, FAN_TURBO]
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: HaierLocalCoordinator, entry: HaierLocalConfigEntry) -> None:
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=entry.title,
            manufacturer="Haier",
            model="uSDK Wi-Fi AC",
        )

    @property
    def hvac_mode(self) -> HVACMode:
        s = self.coordinator.data
        return HVACMode.OFF if not s.power else HVAC_FROM_MODE.get(s.mode, HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        return float(self.coordinator.data.current_temp) or None

    @property
    def target_temperature(self) -> float:
        return float(self.coordinator.data.target_temp)

    @property
    def fan_mode(self) -> str:
        s = self.coordinator.data
        if s.turbo:
            return FAN_TURBO
        if s.quiet:
            return FAN_QUIET
        return FAN_FROM_RAW.get(s.fan, "auto")

    @property
    def swing_mode(self) -> str:
        return SWING_ON if self.coordinator.data.swing_v else SWING_OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set(power=False)
        else:
            await self.coordinator.async_set(power=True, mode=MODE_FROM_HVAC[hvac_mode])

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set(power=True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set(power=False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set(target_temp=round(temp))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if fan_mode == FAN_QUIET:
            await self.coordinator.async_set(quiet=True, turbo=False)
        elif fan_mode == FAN_TURBO:
            await self.coordinator.async_set(turbo=True, quiet=False)
        else:
            await self.coordinator.async_set(fan=RAW_FROM_FAN[fan_mode], quiet=False, turbo=False)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self.coordinator.async_set(swing_v=swing_mode == SWING_ON)
