"""Button platform for Progressive Automations actuator control."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
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

    entities: list[ButtonEntity] = []

    for preset in range(1, 5):
        entities.append(
            RTBT1ActionButton(
                controller,
                f"preset_{preset}",
                f"preset_{preset}",
                f"mdi:numeric-{preset}-box",
                lambda p=preset: controller.async_request_preset_action(p),
                requires_confirmed_unlock=True,
            )
        )

    entities.extend(
        [
            RTBT1ActionButton(
                controller,
                "extend",
                "raise_1s",
                "mdi:arrow-up-bold",
                lambda: controller.async_request_direction(True),
            ),
            RTBT1ActionButton(
                controller,
                "retract",
                "lower_1s",
                "mdi:arrow-down-bold",
                lambda: controller.async_request_direction(False),
            ),
            RTBT1OptionalActionButton(
                controller,
                "fully_extend",
                "fully_extend",
                "mdi:arrow-expand-up",
                lambda: controller.async_request_endpoint(True),
            ),
            RTBT1OptionalActionButton(
                controller,
                "fully_retract",
                "fully_retract",
                "mdi:arrow-collapse-down",
                lambda: controller.async_request_endpoint(False),
            ),
            RTBT1StopButton(
                controller,
                "stop",
                "stop",
                "mdi:stop-circle",
                controller.async_stop,
            ),
            RTBT1TravelLimitButton(
                controller,
                "set_lower_travel_limit",
                "set_lower_travel_limit",
                "mdi:arrow-collapse-down",
                controller.async_set_lower_travel_limit,
                reset=False,
            ),
            RTBT1TravelLimitButton(
                controller,
                "set_upper_travel_limit",
                "set_upper_travel_limit",
                "mdi:arrow-collapse-up",
                controller.async_set_upper_travel_limit,
                reset=False,
            ),
            RTBT1TravelLimitButton(
                controller,
                "reset_travel_limits",
                "reset_travel_limits",
                "mdi:restore",
                controller.async_reset_travel_limits,
                reset=True,
            ),
            RTBT1CalibrationButton(controller),
            RTBT1RehomeButton(controller),
        ]
    )

    async_add_entities(entities)


class RTBT1ActionButton(RTBT1Entity, ButtonEntity):
    """Button backed by an async controller action."""

    def __init__(
        self,
        controller: RTBT1Controller,
        translation_key: str,
        key: str,
        icon: str,
        action: Callable[[], Awaitable[None]],
        *,
        enabled_default: bool = True,
        visible_default: bool = True,
        lock_sensitive: bool = True,
        requires_confirmed_unlock: bool = False,
    ) -> None:
        super().__init__(controller)
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{controller.address}_{key}"
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_entity_registry_visible_default = visible_default
        self._lock_sensitive = lock_sensitive
        self._requires_confirmed_unlock = requires_confirmed_unlock
        self._action = action

    @property
    def available(self) -> bool:
        if self._requires_confirmed_unlock:
            return not self.controller.autonomous_controls_inhibited
        return not (self._lock_sensitive and self.controller.controls_inhibited)

    async def async_press(self) -> None:
        await self._action()


class RTBT1StopButton(RTBT1ActionButton):
    """STOP button with the controller's stricter lock-safety interlock."""

    @property
    def available(self) -> bool:
        return not self.controller.stop_inhibited


class RTBT1OptionalActionButton(RTBT1ActionButton):
    """Optional action disabled and hidden on first entity-registry creation."""

    def __init__(
        self,
        controller: RTBT1Controller,
        translation_key: str,
        key: str,
        icon: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(
            controller,
            translation_key,
            key,
            icon,
            action,
            enabled_default=False,
            visible_default=False,
            requires_confirmed_unlock=True,
        )

class RTBT1TravelLimitButton(RTBT1ActionButton):
    """Controller travel-limit configuration button."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        controller: RTBT1Controller,
        translation_key: str,
        key: str,
        icon: str,
        action: Callable[[], Awaitable[None]],
        *,
        reset: bool,
    ) -> None:
        super().__init__(
            controller,
            translation_key,
            key,
            icon,
            action,
            lock_sensitive=False,
        )
        self._reset = reset

    @property
    def available(self) -> bool:
        state = self.controller.state
        common = (
            state.locked is False
            and not self.controller.travel_limit_active
            and not self.controller.calibration_active
            and not self.controller.rehome_active
            and not self.controller.motion_active
            and self.controller.lock_transition_target is None
        )
        if not common:
            return False
        if self._reset:
            return state.lower_limit is not None or state.upper_limit is not None
        return state.position is not None


class RTBT1RehomeButton(RTBT1ActionButton):
    """Advanced RST/re-home recovery control, disabled by default."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(
            controller,
            "rst_rehome_actuator",
            "rst_rehome_actuator",
            "mdi:restart",
            controller.async_request_rst_rehome,
            enabled_default=False,
            visible_default=True,
            lock_sensitive=False,
        )

    @property
    def available(self) -> bool:
        # RST is intentionally usable as a recovery action while Control Lock is
        # Locked/Unknown, but never while another HA motion or lock transition is
        # already active.
        return (
            not self.controller.rehome_active
            and not self.controller.travel_limit_active
            and not self.controller.motion_active
            and self.controller.lock_transition_target is None
        )


class RTBT1CalibrationButton(RTBT1ActionButton):
    """Intentional full-travel physical position calibration control."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(
            controller,
            "calibrate_position_range",
            "calibrate_position_range",
            "mdi:tape-measure",
            controller.async_request_position_calibration,
            enabled_default=False,
            visible_default=True,
            lock_sensitive=False,
        )

    @property
    def available(self) -> bool:
        state = self.controller.state
        return (
            state.locked is False
            and state.lower_limit is None
            and state.upper_limit is None
            and not self.controller.calibration_active
            and not self.controller.travel_limit_active
            and not self.controller.rehome_active
            and not self.controller.motion_active
            and self.controller.lock_transition_target is None
        )

