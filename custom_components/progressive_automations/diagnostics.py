"""Diagnostics support for Progressive Automations."""

from __future__ import annotations

import re
from time import monotonic
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_ADDRESS, DOMAIN
from .controller import RTBT1Controller

TO_REDACT = {CONF_ADDRESS}
_MAC_RE = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")


def _redact_mac_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _MAC_RE.sub("**REDACTED**", value)


def _iso(value: object | None) -> str | None:
    return None if value is None else value.isoformat()


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return safe diagnostics for a Progressive Automations config entry."""
    controller: RTBT1Controller | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    state: dict[str, Any] | None = None
    reachability: str | None = None

    if controller is not None:
        current = controller.state
        state = {
            "position_raw": current.position,
            "extension_in": current.extension_inches,
            "position_percent": current.position_percent,
            "position_calibration": controller.calibration_state,
            "physical_min_raw": current.physical_min,
            "physical_max_raw": current.physical_max,
            "status_byte": current.status_byte,
            "presets_raw": dict(sorted(current.presets.items())),
            "lower_limit_raw": current.lower_limit,
            "upper_limit_raw": current.upper_limit,
            "calibration_storage": "home_assistant_store_device_key",
            "limit_flags": current.limit_flags,
            "locked": current.locked,
            "controller_error_code": current.error_code,
            "target_extension_in": current.target_extension_inches,
            "target_percent": current.target_position_percent,
            "protocol_variant": current.protocol_variant,
            "connected": current.connected,
            "activity": current.activity,
            "last_error": current.last_error,
            "program_preset_mode": controller.program_preset_mode,
            "travel_limit_operation_active": controller.travel_limit_active,
            "diagnostics": {
                "scope": {
                    "counter_scope": "since_integration_load",
                    "integration_load_time_utc": _iso(controller.diag_session_started_at_utc),
                },
                "operation": {
                    "activity": current.activity,
                    "previous_activity": controller.diag_previous_activity,
                    "activity_transitions": controller.diag_activity_transitions,
                    "activity_age_seconds": (
                        None
                        if controller.diag_activity_changed_at is None
                        else round(monotonic() - controller.diag_activity_changed_at, 1)
                    ),
                    "motion_active": controller.motion_active,
                    "rst_rehome_active": controller.rehome_active,
                    "position_calibration_active": controller.calibration_active,
                    "travel_limit_operation_active": controller.travel_limit_active,
                    "lock_transition_target": controller.lock_transition_target,
                },
                "communications": {
                    "last_successful_communication_utc": _iso(
                        controller.diag_last_successful_communication_at_utc
                    ),
                    "last_error": controller.diag_last_error_message,
                    "last_error_utc": _iso(controller.diag_last_error_at_utc),
                },
                "protocol": {
                    "fe61_writes": controller.diag_fe61_writes,
                    "fe62_frames": controller.diag_fe62_frames,
                    "fe62_checksum_errors": controller.diag_fe62_checksum_errors,
                    "fe62_parse_errors": controller.diag_fe62_parse_errors,
                    "fe62_recovered_frames": controller.diag_fe62_recovered_frames,
                    "ble_sessions": controller.diag_ble_sessions,
                    "last_fe62_age_seconds": (
                        None
                        if controller.diag_last_fe62_at is None
                        else round(monotonic() - controller.diag_last_fe62_at, 1)
                    ),
                    "parser": {
                        "last_error_reason": controller.diag_last_parse_error_reason,
                        "last_error_payload_hex": controller.diag_last_parse_error_payload,
                        "last_error_age_seconds": (
                            None
                            if controller.diag_last_parse_error_at is None
                            else round(monotonic() - controller.diag_last_parse_error_at, 1)
                        ),
                        "last_recovery_reason": controller.diag_last_recovery_reason,
                        "last_recovery_payload_hex": controller.diag_last_recovery_payload,
                        "last_recovery_age_seconds": (
                            None
                            if controller.diag_last_recovery_at is None
                            else round(monotonic() - controller.diag_last_recovery_at, 1)
                        ),
                    },
                    "last_action_command": {
                        "name": controller.diag_last_command_name,
                        "opcode": controller.diag_last_command_opcode,
                        "payload_hex": controller.diag_last_command_payload,
                        "result": controller.diag_last_command_result,
                        "age_seconds": (
                            None
                            if controller.diag_last_command_at is None
                            else round(monotonic() - controller.diag_last_command_at, 1)
                        ),
                    },
                    "gatt_write_attempts": controller.diag_gatt_write_attempts,
                    "gatt_write_failures": controller.diag_gatt_write_failures,
                    "gatt_write_counts": dict(sorted(controller.diag_gatt_write_counts.items())),
                    "last_gatt_write": {
                        "name": controller.diag_last_gatt_write_name,
                        "opcode": controller.diag_last_gatt_write_opcode,
                        "payload_hex": controller.diag_last_gatt_write_payload,
                        "result": controller.diag_last_gatt_write_result,
                        "age_seconds": (
                            None
                            if controller.diag_last_gatt_write_at is None
                            else round(monotonic() - controller.diag_last_gatt_write_at, 1)
                        ),
                    },
                    "rx_command_counts": dict(sorted(controller.diag_rx_command_counts.items())),
                    "last_rx_frame": {
                        "name": controller.diag_last_rx_name,
                        "opcode": controller.diag_last_rx_opcode,
                        "payload_hex": controller.diag_last_rx_payload,
                        "age_seconds": (
                            None
                            if controller.diag_last_rx_at is None
                            else round(monotonic() - controller.diag_last_rx_at, 1)
                        ),
                    },
                },
                "rst_rehome": {
                    "requests": controller.diag_rst_requests,
                    "completed": controller.diag_rst_completed,
                    "failures": controller.diag_rst_failures,
                    "rst_response_frames": controller.diag_rst_response_frames,
                    "last_result": controller.diag_last_rst_result,
                },
                "position_calibration": {
                    "requests": controller.diag_calibration_requests,
                    "completed": controller.diag_calibration_completed,
                    "failures": controller.diag_calibration_failures,
                    "stopped": controller.diag_calibration_stopped,
                    "last_result": controller.diag_last_calibration_result,
                    "physical_min_raw": current.physical_min,
                    "physical_max_raw": current.physical_max,
                },
                "travel_limits": {
                    "current": {
                        "lower_raw": current.lower_limit,
                        "upper_raw": current.upper_limit,
                        "limit_flags": current.limit_flags,
                        "status_frame_age_seconds": (
                            None
                            if controller.diag_last_limit_status_at is None
                            else round(monotonic() - controller.diag_last_limit_status_at, 1)
                        ),
                        "authoritative_snapshot_available": (
                            controller.diag_last_travel_limit_snapshot_at is not None
                        ),
                        "authoritative_snapshot_age_seconds": (
                            None
                            if controller.diag_last_travel_limit_snapshot_at is None
                            else round(
                                monotonic() - controller.diag_last_travel_limit_snapshot_at, 1
                            )
                        ),
                        "authoritative_snapshot_utc": _iso(
                            controller.diag_last_travel_limit_snapshot_at_utc
                        ),
                        "snapshot_lower_raw": (
                            controller.diag_last_travel_limit_snapshot_lower
                        ),
                        "snapshot_upper_raw": (
                            controller.diag_last_travel_limit_snapshot_upper
                        ),
                    },
                    "lower": {
                        "raw": current.lower_limit,
                        "requests": controller.diag_lower_limit_requests,
                        "gatt_writes": controller.diag_lower_limit_writes,
                        "verified": controller.diag_lower_limit_verified,
                        "last_result": controller.diag_last_lower_limit_result,
                    },
                    "upper": {
                        "raw": current.upper_limit,
                        "requests": controller.diag_upper_limit_requests,
                        "gatt_writes": controller.diag_upper_limit_writes,
                        "verified": controller.diag_upper_limit_verified,
                        "last_result": controller.diag_last_upper_limit_result,
                    },
                    "reset": {
                        "requests": controller.diag_reset_requests,
                        "gatt_writes": controller.diag_reset_writes,
                        "preflight_queries": controller.diag_reset_preflight_queries,
                        "preflight_confirmed": controller.diag_reset_preflight_confirmed,
                        "verification_queries": controller.diag_reset_verification_queries,
                        "verified_clears": controller.diag_reset_verified_clears,
                        "last_result": controller.diag_last_reset_result,
                    },
                },
            },
        }

        try:
            reachability = _redact_mac_text(
                bluetooth.async_address_reachability_diagnostics(
                    hass,
                    controller.address,
                    BluetoothReachabilityIntent.CONNECTION,
                )
            )
        except Exception:
            reachability = "unavailable"

    rssi: int | None = None
    if controller is not None:
        try:
            service_info = bluetooth.async_last_service_info(
                hass,
                controller.address,
                connectable=True,
            )
            if service_info is not None:
                rssi = getattr(service_info, "rssi", None)
        except Exception:
            pass

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "connection": {
            "transport": "Bluetooth Low Energy",
            "adapter_interface": "Progressive Automations RT-BT1",
            "reachability": reachability,
            "rssi_dbm": rssi,
        },
        "state": state,
    }
