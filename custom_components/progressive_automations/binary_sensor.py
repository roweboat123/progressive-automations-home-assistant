"""Binary diagnostic sensors for Progressive Automations RT-BT1."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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
    async_add_entities([RTBT1ProblemBinarySensor(controller)])


class RTBT1ProblemBinarySensor(RTBT1Entity, BinarySensorEntity):
    """Whether the most recent controller operation recorded an error."""

    _attr_translation_key = "communication_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_communication_problem"

    @property
    def is_on(self) -> bool:
        return self.controller.state.last_error is not None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        error = self.controller.state.last_error
        if error is None:
            return None
        return {"message": error}
