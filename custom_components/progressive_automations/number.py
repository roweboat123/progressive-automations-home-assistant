"""Number platform for Progressive Automations RT-BT1 position control."""

from __future__ import annotations

import math

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up the user-facing percentage position control."""
    controller: RTBT1Controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RTBT1PositionPercentNumber(controller)])


class RTBT1PositionPercentNumber(RTBT1Entity, NumberEntity):
    """Native absolute-position control expressed as 0-100 percent."""

    _attr_translation_key = "position_percentage_control"
    _attr_icon = "mdi:percent-box-outline"
    _attr_native_unit_of_measurement = "%"
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_target_percent"

    @property
    def available(self) -> bool:
        state = self.controller.state
        return (
            not self.controller.autonomous_controls_inhibited
            and state.position is not None
            and state.physical_min is not None
            and state.physical_max is not None
            and state.physical_max > state.physical_min
        )

    def _allowed_percent_bounds(self) -> tuple[float, float]:
        """Return absolute physical-percentage bounds allowed by user limits."""
        state = self.controller.state
        physical_min = state.physical_min
        physical_max = state.physical_max
        if (
            physical_min is None
            or physical_max is None
            or physical_max <= physical_min
        ):
            return 0.0, 100.0

        span = float(physical_max - physical_min)
        allowed_min = 0.0
        allowed_max = 100.0

        if state.lower_limit is not None:
            raw = 100.0 * (float(state.lower_limit) - physical_min) / span
            # The Number entity has a 1% step. Round inward so an accepted
            # integer request can never command beyond the programmed limit.
            allowed_min = float(max(0, min(100, math.ceil(raw - 1e-9))))

        if state.upper_limit is not None:
            raw = 100.0 * (float(state.upper_limit) - physical_min) / span
            allowed_max = float(max(0, min(100, math.floor(raw + 1e-9))))

        if allowed_min > allowed_max:
            # Defensive fallback for a transient/inconsistent controller snapshot.
            return 0.0, 100.0
        return allowed_min, allowed_max

    @property
    def native_min_value(self) -> float:
        """Minimum accepted absolute physical percentage."""
        return self._allowed_percent_bounds()[0]

    @property
    def native_max_value(self) -> float:
        """Maximum accepted absolute physical percentage."""
        return self._allowed_percent_bounds()[1]

    @property
    def extra_state_attributes(self) -> dict[str, float]:
        """Expose the invariant physical scale and current hard fences."""
        allowed_min, allowed_max = self._allowed_percent_bounds()
        return {
            "physical_scale_min_percent": 0.0,
            "physical_scale_max_percent": 100.0,
            "allowed_min_percent": allowed_min,
            "allowed_max_percent": allowed_max,
        }

    @property
    def native_value(self) -> float | None:
        """Return the live position percentage rounded to the 1% control step."""
        value = self.controller.state.position_percent
        return None if value is None else float(round(value))

    async def async_set_native_value(self, value: float) -> None:
        """Convert calibrated physical percentage, clamp limits, then use 0x1B."""
        await self.controller.async_request_percent(float(value))
