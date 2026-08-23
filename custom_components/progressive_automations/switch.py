"""Switch platform for Progressive Automations RT-BT1 controls."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import RTBT1Controller
from .entity import RTBT1Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: RTBT1Controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RTBT1ProgramPresetSwitch(controller)])


class RTBT1ProgramPresetSwitch(RTBT1Entity, SwitchEntity):
    """Arm one-shot preset programming mode."""

    _attr_translation_key = "program_preset"
    _attr_icon = "mdi:content-save-cog"

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_program_preset"

    @property
    def available(self) -> bool:
        return not self.controller.autonomous_controls_inhibited

    @property
    def is_on(self) -> bool:
        return self.controller.program_preset_mode

    async def async_turn_on(self, **kwargs) -> None:
        await self.controller.async_set_program_preset_mode(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.controller.async_set_program_preset_mode(False)

