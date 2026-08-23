"""Shared entity helpers for Progressive Automations RT-BT1."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import RTBT1Controller


class RTBT1Entity(Entity):
    """Base entity for one Progressive Automations Bluetooth actuator-control system."""

    _attr_has_entity_name = True

    def __init__(self, controller: RTBT1Controller) -> None:
        self.controller = controller
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.address)},
            name="Bluetooth Actuator Control",
            translation_key="bluetooth_actuator_control",
            manufacturer="Progressive Automations",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.controller.add_listener(self.async_write_ha_state)
        )
