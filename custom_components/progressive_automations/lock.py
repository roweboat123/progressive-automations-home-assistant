"""Lock platform for Progressive Automations RT-BT1 control lock."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
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
    async_add_entities([RTBT1ControlLock(controller)])


class RTBT1ControlLock(RTBT1Entity, LockEntity):
    """Native Home Assistant lock entity for the vendor control lock."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "control_lock"
    _attr_entity_registry_enabled_default = False
    _attr_entity_registry_visible_default = True

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_control_lock"

    @property
    def available(self) -> bool:
        return not self.controller.rehome_active

    @property
    def is_locked(self) -> bool | None:
        return self.controller.state.locked

    @property
    def is_locking(self) -> bool:
        return self.controller.lock_transition_target is True

    @property
    def is_unlocking(self) -> bool:
        return self.controller.lock_transition_target is False

    async def async_lock(self, **kwargs) -> None:
        await self.controller.async_set_lock(True)

    async def async_unlock(self, **kwargs) -> None:
        await self.controller.async_set_lock(False)
