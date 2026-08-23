"""Sensor platform for Progressive Automations RT-BT1."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import RTBT1Controller
from .entity import RTBT1Entity


def _humanize_command_name(value: str | None) -> str | None:
    """Return a user-facing label while preserving raw names in diagnostics."""
    if value is None:
        return None
    labels = {
        "extend": "Fully Extend",
        "retract": "Fully Retract",
        "save_preset_1": "Save Preset 1",
        "save_preset_2": "Save Preset 2",
        "save_preset_3": "Save Preset 3",
        "save_preset_4": "Save Preset 4",
        "move_preset_1": "Preset 1",
        "move_preset_2": "Preset 2",
        "move_preset_3": "Preset 3",
        "move_preset_4": "Preset 4",
        "momentary_release": "Momentary Release",
        "move_absolute": "Move to Position",
        "save_upper_travel_limit": "Set Upper Travel Limit",
        "save_lower_travel_limit": "Set Lower Travel Limit",
        "reset_travel_limits": "Reset Travel Limits",
        "toggle_control_lock": "Control Lock Toggle",
        "stop": "Stop",
    }
    return labels.get(value, value.replace("_", " ").title())


def _humanize_command_result(value: str | None) -> str | None:
    """Return a compact user-facing command result label."""
    if value is None:
        return None
    labels = {
        "attempting": "Attempting",
        "completed": "Completed",
        "failed": "Failed",
    }
    return labels.get(value, value.replace("_", " ").title())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: RTBT1Controller = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            RTBT1ExtensionSensor(controller),
            RTBT1PositionPercentSensor(controller),
            RTBT1PositionCalibrationSensor(controller),
            RTBT1OperationStatusSensor(controller),
            RTBT1TravelLimitSensor(controller, upper=False),
            RTBT1TravelLimitSensor(controller, upper=True),
            RTBT1RSSISensor(controller),
            RTBT1LastSuccessfulCommunicationSensor(controller),
            RTBT1LastCommandSensor(controller),
            RTBT1LastCommandResultSensor(controller),
            RTBT1LastErrorSensor(controller),
            RTBT1DiagnosticSensor(
                controller,
                "controller_error_code",
                "controller_error_code",
                "mdi:alert-octagon-outline",
                lambda c: c.state.error_code,
            ),
        ]
    )


class RTBT1ExtensionSensor(RTBT1Entity, SensorEntity):
    """Current actuator extension."""

    _attr_translation_key = "extension"
    _attr_icon = "mdi:arrow-expand-horizontal"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.INCHES
    # Keep inches as the initial presentation while allowing Home Assistant's
    # native sensor options to convert the entity to mm (or another supported
    # distance unit) without changing any RT-BT1 protocol calculations.
    _attr_suggested_unit_of_measurement = UnitOfLength.INCHES
    _attr_suggested_display_precision = 1
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_extension"

    @property
    def native_value(self) -> float | None:
        return self.controller.state.extension_inches

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose useful actuator state without developer/debug internals."""
        state = self.controller.state
        attrs: dict[str, object] = {
            "position_percent": (
                None
                if state.position_percent is None
                else round(state.position_percent, 1)
            ),
        }

        if state.target_extension_inches is not None:
            attrs["target_extension_in"] = state.target_extension_inches
        if state.target_position_percent is not None:
            attrs["target_percent"] = round(state.target_position_percent, 1)

        if state.lower_limit is not None:
            attrs["lower_limit_in"] = state.lower_limit / 10.0
        if state.upper_limit is not None:
            attrs["upper_limit_in"] = state.upper_limit / 10.0

        for preset, raw in sorted(state.presets.items()):
            attrs[f"preset_{preset}_in"] = raw / 10.0

        return attrs


class RTBT1PositionPercentSensor(RTBT1Entity, SensorEntity):
    """Current actuator position expressed across calibrated physical travel."""

    _attr_translation_key = "position_percentage"
    _attr_icon = "mdi:percent"
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 0
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_position_percent"

    @property
    def available(self) -> bool:
        state = self.controller.state
        return (
            state.position is not None
            and state.physical_min is not None
            and state.physical_max is not None
            and state.physical_max > state.physical_min
        )

    @property
    def native_value(self) -> float | None:
        return self.controller.state.position_percent


class RTBT1PositionCalibrationSensor(RTBT1Entity, SensorEntity):
    """Report whether the installation-specific physical range is calibrated."""

    _attr_translation_key = "position_calibration"
    _attr_icon = "mdi:map-marker-distance"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["required", "calibrating", "calibrated"]
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_position_calibration"

    @property
    def native_value(self) -> str:
        return self.controller.calibration_state

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        state = self.controller.state
        attrs: dict[str, object] = {}
        if state.physical_min is not None:
            attrs["physical_min_in"] = state.physical_min / 10.0
        if state.physical_max is not None:
            attrs["physical_max_in"] = state.physical_max / 10.0
        return attrs


class RTBT1OperationStatusSensor(RTBT1Entity, SensorEntity):
    """Human-readable feedback for long-running controller operations."""

    _attr_translation_key = "operation_status"
    _attr_icon = "mdi:progress-wrench"
    _attr_should_poll = False

    _LABELS = {
        "idle": "Idle",
        "connecting": "Connecting",
        "connected": "Connected",
        "refreshing": "Refreshing controller state",
        "extending_momentary": "Extending",
        "retracting_momentary": "Retracting",
        "fully_extending": "Fully extending",
        "fully_retracting": "Fully retracting",
        "moving_to_position": "Moving to position",
        "stopping": "Stopping",
        "locking": "Locking controls",
        "unlocking": "Unlocking controls",
        "setting_lower_travel_limit": "Setting lower travel limit",
        "setting_upper_travel_limit": "Setting upper travel limit",
        "preparing_travel_limit_reset": "Preparing travel-limit reset",
        "resetting_travel_limits": "Resetting travel limits",
        "verifying_travel_limit_reset": "Verifying travel-limit reset",
        "position_calibration_checking_limits": "Checking travel limits before calibration",
        "position_calibration_finding_lower": "Calibrating lower endpoint",
        "position_calibration_finding_upper": "Calibrating upper endpoint",
        "position_calibration_restoring": "Returning to pre-calibration position",
        "rst_rehome_descending": "RST: moving to lower endpoint",
        "rst_rehome_cooldown": "RST: settling",
        "rst_rehome_waiting_for_rst": "RST: waiting for controller reset state",
        "rst_rehome_rehoming": "RST: re-homing actuator",
        "rst_rehome_refreshing": "RST: refreshing controller state",
    }

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_operation_status"

    @property
    def native_value(self) -> str:
        activity = self.controller.state.activity
        if activity.startswith("preset_"):
            return f"Moving to preset {activity.removeprefix('preset_')}"
        if activity.startswith("saving_preset_"):
            return f"Saving preset {activity.removeprefix('saving_preset_')}"
        return self._LABELS.get(activity, activity.replace("_", " ").strip().capitalize())

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "activity_code": self.controller.state.activity,
            "motion_active": self.controller.motion_active,
            "rst_rehome_active": self.controller.rehome_active,
            "position_calibration_active": self.controller.calibration_active,
            "travel_limit_operation_active": self.controller.travel_limit_active,
        }


class RTBT1TravelLimitSensor(RTBT1Entity, SensorEntity):
    """Report one programmed controller travel limit in physical inches."""

    # These are configuration readbacks, not live distance measurements. Keep
    # them as plain numeric sensors so HA displays the raw controller value
    # directly; an unset limit remains an unknown value rather than making the
    # entity itself unavailable.
    _attr_native_unit_of_measurement = UnitOfLength.INCHES
    _attr_suggested_display_precision = 1
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller, *, upper: bool) -> None:
        super().__init__(controller)
        self._upper = upper
        key = "upper_travel_limit" if upper else "lower_travel_limit"
        self._attr_translation_key = key
        self._attr_unique_id = f"{controller.address}_{key}"
        self._attr_icon = "mdi:arrow-collapse-up" if upper else "mdi:arrow-collapse-down"

    @property
    def available(self) -> bool:
        """Keep the readback entity available even when no limit is programmed."""
        return True

    @property
    def native_value(self) -> float | None:
        raw = self.controller.state.upper_limit if self._upper else self.controller.state.lower_limit
        return None if raw is None else raw / 10.0

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        raw = self.controller.state.upper_limit if self._upper else self.controller.state.lower_limit
        snapshot_at = self.controller.diag_last_travel_limit_snapshot_at
        return {
            "programmed": raw is not None,
            "raw_position": raw,
            "authoritative_snapshot_age_seconds": (
                None if snapshot_at is None else round(monotonic() - snapshot_at, 1)
            ),
        }


class RTBT1DiagnosticSensor(RTBT1Entity, SensorEntity):
    """Simple opt-in diagnostic sensor backed by passive controller state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        controller: RTBT1Controller,
        translation_key: str,
        key: str,
        icon: str,
        getter: Callable[[RTBT1Controller], Any],
    ) -> None:
        super().__init__(controller)
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{controller.address}_{key}"
        self._attr_icon = icon
        self._getter = getter

    @property
    def native_value(self) -> Any:
        return self._getter(self.controller)


class RTBT1RSSISensor(RTBT1Entity, SensorEntity):
    """Best current connectable advertisement RSSI from Home Assistant Bluetooth."""

    _attr_translation_key = "rssi"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = "dBm"
    _attr_icon = "mdi:signal"
    _attr_should_poll = True

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_rssi"
        self._rssi: int | None = None

    async def async_update(self) -> None:
        service_info = bluetooth.async_last_service_info(
            self.controller.hass,
            self.controller.address,
            connectable=True,
        )
        self._rssi = None if service_info is None else getattr(service_info, "rssi", None)

    @property
    def native_value(self) -> int | None:
        return self._rssi


class RTBT1LastSuccessfulCommunicationSensor(RTBT1Entity, SensorEntity):
    """Timestamp of the most recent valid protocol frame received from RT-BT1."""

    _attr_translation_key = "last_successful_communication"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:check-network-outline"
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_last_successful_communication"

    @property
    def native_value(self):
        return self.controller.diag_last_successful_communication_at_utc


class RTBT1LastCommandSensor(RTBT1Entity, SensorEntity):
    """Most recent outbound integration command."""

    _attr_translation_key = "last_command"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:bluetooth-transfer"
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_last_command"

    @property
    def native_value(self) -> str | None:
        return _humanize_command_name(self.controller.diag_last_command_name)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "opcode": self.controller.diag_last_command_opcode,
            "payload_hex": self.controller.diag_last_command_payload,
            "result": self.controller.diag_last_command_result,
        }


class RTBT1LastCommandResultSensor(RTBT1Entity, SensorEntity):
    """Result of the most recent outbound integration command."""

    _attr_translation_key = "last_command_result"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:check-decagram-outline"
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_last_command_result"

    @property
    def native_value(self) -> str | None:
        return _humanize_command_result(self.controller.diag_last_command_result)


class RTBT1LastErrorSensor(RTBT1Entity, SensorEntity):
    """Most recent integration/controller error retained for diagnostics."""

    _attr_translation_key = "last_error"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:alert-circle-outline"
    _attr_should_poll = False

    def __init__(self, controller: RTBT1Controller) -> None:
        super().__init__(controller)
        self._attr_unique_id = f"{controller.address}_last_error"

    @property
    def native_value(self) -> str | None:
        message = self.controller.diag_last_error_message
        if message is None:
            return None
        return message[:255]

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "message": self.controller.diag_last_error_message,
            "occurred_at": self.controller.diag_last_error_at_utc,
        }
