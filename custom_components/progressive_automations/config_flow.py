"""Config flow for Progressive Automations Bluetooth actuator control."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ADDRESS, DOMAIN, V1_SERVICE_UUID, V2_SERVICE_UUID

_LOGGER = logging.getLogger(__name__)

DEFAULT_TITLE = "Bluetooth Actuator Control"
MANUAL_ENTRY = "__manual__"
SCAN_DURATION = 8.0

MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
SUPPORTED_SERVICE_UUIDS = {
    "fe60",
    "ff12",
    V2_SERVICE_UUID.lower(),
    V1_SERVICE_UUID.lower(),
}


def _clean_name(value: str | None) -> str | None:
    """Normalize a discovered Bluetooth name."""
    if not value:
        return None
    value = value.strip().strip("\x00")
    return value or None


def _candidate_names(info: BluetoothServiceInfoBleak) -> list[str]:
    """Return every useful name HA/Bleak may expose for this advertisement."""
    names: list[str] = []

    for value in (
        getattr(info, "name", None),
        getattr(getattr(info, "advertisement", None), "local_name", None),
        getattr(getattr(info, "device", None), "name", None),
    ):
        name = _clean_name(value)
        if name and name not in names:
            names.append(name)

    return names


def _looks_like_progressive_automations(info: BluetoothServiceInfoBleak) -> bool:
    """Return True when advertisement metadata resembles the tested RT-BT1."""
    for name in _candidate_names(info):
        if name.upper().startswith("BLE DEVICE"):
            return True

    for uuid in getattr(info, "service_uuids", []) or []:
        if str(uuid).lower() in SUPPORTED_SERVICE_UUIDS:
            return True

    return False


def _best_display_name(info: BluetoothServiceInfoBleak) -> str:
    """Choose the most useful human-readable label available."""
    names = _candidate_names(info)

    for name in names:
        if not MAC_RE.match(name):
            return name

    if names:
        return names[0]

    return "Unnamed Bluetooth device"


class ProgressiveAutomationsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Progressive Automations setup."""

    VERSION = 1
    MINOR_VERSION = 4

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._scan_results: dict[str, str] = {}

    def _configured_addresses(self) -> set[str]:
        """Return addresses already configured for this integration."""
        return {
            str(entry.data.get(CONF_ADDRESS, "")).upper()
            for entry in self._async_current_entries()
            if entry.data.get(CONF_ADDRESS)
        }

    async def _async_create_entry(self, address: str) -> FlowResult:
        """Create an entry for a selected Bluetooth adapter."""
        address = address.strip().upper()

        await self.async_set_unique_id(address, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": DEFAULT_TITLE}

        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data={CONF_ADDRESS: address},
        )

    async def _async_collect_candidates(self) -> dict[str, str]:
        """Collect nearby connectable BLE devices, prioritizing likely RT-BT1s."""
        configured = self._configured_addresses()
        callback_matches: dict[str, BluetoothServiceInfoBleak] = {}

        def _async_discovered(
            service_info: BluetoothServiceInfoBleak,
            change: BluetoothChange,
        ) -> None:
            """Capture live local-name matches during this setup scan."""
            address = service_info.address.upper()
            if address not in configured:
                callback_matches[address] = service_info

        cancel_callback = bluetooth.async_register_callback(
            self.hass,
            _async_discovered,
            {"local_name": "BLE DEVICE *", "connectable": True},
            BluetoothScanningMode.ACTIVE,
        )

        try:
            try:
                await bluetooth.async_request_active_scan(
                    self.hass,
                    duration=SCAN_DURATION,
                )
            except Exception:
                _LOGGER.debug(
                    "On-demand Bluetooth scan request failed; using live/cache results",
                    exc_info=True,
                )
        finally:
            cancel_callback()

        infos_by_address: dict[str, BluetoothServiceInfoBleak] = {}
        infos_by_address.update(callback_matches)

        for info in bluetooth.async_discovered_service_info(
            self.hass,
            connectable=True,
        ):
            address = info.address.upper()
            if address in configured:
                continue
            infos_by_address.setdefault(address, info)

        likely: list[tuple[int, str, BluetoothServiceInfoBleak]] = []

        for address, info in infos_by_address.items():
            if not _looks_like_progressive_automations(info):
                continue

            rssi = int(getattr(info, "rssi", -999) or -999)
            likely.append((-rssi, address, info))

        likely.sort()

        _LOGGER.debug(
            "Progressive Automations setup scan likely devices: %s",
            [
                {
                    "address": address,
                    "names": _candidate_names(info),
                    "rssi": getattr(info, "rssi", None),
                    "service_uuids": list(
                        getattr(info, "service_uuids", []) or []
                    ),
                }
                for _, address, info in likely
            ],
        )

        choices: dict[str, str] = {}

        # The MAC remains the internal selector VALUE because it is what the
        # config entry needs, but it is intentionally not repeated in the label.
        # With one device the user simply sees "Bluetooth Actuator Control".
        # With multiple devices we add the BLE advertising name for distinction.
        multiple = len(likely) > 1

        for _, address, info in likely:
            if multiple:
                display_name = _best_display_name(info)
                label = f"RT-BT1 — {display_name}"
            else:
                label = "RT-BT1"

            choices[address] = label

        return choices

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Start setup by scanning for nearby Bluetooth devices."""
        self.context["title_placeholders"] = {"name": DEFAULT_TITLE}
        return await self.async_step_scan()

    async def async_step_scan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Run the Bluetooth scan and show a normal selector form."""
        self.context["title_placeholders"] = {"name": DEFAULT_TITLE}

        if bluetooth.async_scanner_count(self.hass, connectable=True) == 0:
            return await self.async_step_no_scanner()

        self._scan_results = await self._async_collect_candidates()

        if not self._scan_results:
            return await self.async_step_no_devices()

        return await self.async_step_scan_results()

    async def async_step_scan_results(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Let the user choose a discovered Bluetooth device."""
        if user_input is not None:
            selected = user_input["Auto Discovery"]

            if selected == MANUAL_ENTRY:
                return await self.async_step_manual()

            # The selector's UI field is intentionally named "auto_discovery".
            # Only the selected value is stored as CONF_ADDRESS in the entry.
            return await self._async_create_entry(selected)

        choices: dict[str, str] = dict(self._scan_results)
        choices[MANUAL_ENTRY] = "Enter Bluetooth address manually"

        return self.async_show_form(
            step_id="scan_results",
            data_schema=vol.Schema(
                {vol.Required("Auto Discovery"): vol.In(choices)}
            ),
        )

    async def async_step_no_devices(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Retry scanning or accept a manually entered Bluetooth address."""
        self.context["title_placeholders"] = {"name": DEFAULT_TITLE}
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input.get(CONF_ADDRESS, "").strip().upper()

            if not address:
                return await self.async_step_scan()

            if not MAC_RE.match(address):
                errors["base"] = "invalid_address"
            else:
                return await self._async_create_entry(address)

        return self.async_show_form(
            step_id="no_devices",
            data_schema=vol.Schema(
                {vol.Optional(CONF_ADDRESS, default=""): str}
            ),
            errors=errors,
        )

    async def async_step_no_scanner(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Accept manual address when HA has no connectable Bluetooth scanner."""
        self.context["title_placeholders"] = {"name": DEFAULT_TITLE}
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()

            if not MAC_RE.match(address):
                errors["base"] = "invalid_address"
            else:
                return await self._async_create_entry(address)

        return self.async_show_form(
            step_id="no_scanner",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS, default=""): str}
            ),
            errors=errors,
        )

    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> FlowResult:
        """Handle native Home Assistant Bluetooth discovery."""
        if not discovery_info.connectable:
            return self.async_abort(reason="not_supported")

        if not _looks_like_progressive_automations(discovery_info):
            return self.async_abort(reason="not_supported")

        address = discovery_info.address.upper()
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": DEFAULT_TITLE}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Confirm a natively discovered Bluetooth adapter."""
        if self._discovery_info is None:
            return self.async_abort(reason="not_supported")

        if user_input is not None:
            return await self._async_create_entry(
                self._discovery_info.address
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "adapter": "RT-BT1",
            },
        )

    async def async_step_manual(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle manual Bluetooth-address entry."""
        self.context["title_placeholders"] = {"name": DEFAULT_TITLE}
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()

            if not MAC_RE.match(address):
                errors["base"] = "invalid_address"
            else:
                return await self._async_create_entry(address)

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDRESS,
                        default=(user_input or {}).get(CONF_ADDRESS, ""),
                    ): str
                }
            ),
            errors=errors,
        )
