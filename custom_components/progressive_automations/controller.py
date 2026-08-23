"""BLE protocol controller for Progressive Automations RT-BT1."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import math
from time import monotonic

from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    PRESET_RESPONSE,
    ERROR_RESPONSE,
    LIMIT_FLAGS_RESPONSE,
    LOCK_RESPONSE,
    LOWER,
    MAX_LIMIT_RESPONSE,
    MIN_LIMIT_RESPONSE,
    MOM_RELEASE,
    MOVE_PRESET,
    OPT_PHYSICAL_MAX_RAW,
    OPT_PHYSICAL_MIN_RAW,
    POSITION_RESPONSE,
    QUERY_LIMITS,
    QUERY_STATUS,
    RAISE,
    RST_RESPONSE,
    SAVE_PRESET,
    SAVE_UPPER_LIMIT,
    SAVE_LOWER_LIMIT,
    RESET_TRAVEL_LIMITS,
    LOCK_QUERY,
    LOCK_TOGGLE,
    STOP,
    V1_NOTIFY_UUID,
    V1_SERVICE_UUID,
    V1_WRITE_UUID,
    V2_NOTIFY_UUID,
    V2_SERVICE_UUID,
    V2_WRITE_UUID,
    build_move_to_position,
)

_LOGGER = logging.getLogger(__name__)

Listener = Callable[[], None]
MotionFactory = Callable[[], Awaitable[None]]

IDLE_DISCONNECT_SECONDS = 60.0
WAKE_AFTER_SECONDS = 5.0
WAKE_SETTLE_SECONDS = 0.35
REPEAT_INTERVAL_SECONDS = 0.20
MOMENTARY_DURATION_SECONDS = 0.125
ENDPOINT_STABLE_SECONDS = 1.4
ENDPOINT_TIMEOUT_SECONDS = 45.0

# Progressive Motion RST/re-home sequence. Hardware capture shows ordinary DOWN
# writes at ~200 ms, a one-second pause before/after the RST response, and the
# exact FLTCON-1 reset-state frame F2 F2 04 00 04 7E.
REHOME_STABLE_SAMPLES = 6
REHOME_DESCEND_TIMEOUT_SECONDS = 50.0
REHOME_RST_TIMEOUT_SECONDS = 15.0
REHOME_NORMAL_TIMEOUT_SECONDS = 15.0
REHOME_COOLDOWN_SECONDS = 1.0

# Physical-range calibration deliberately uses the same fresh-position,
# six-identical-sample endpoint criterion that proved reliable during RST testing.
CALIBRATION_STABLE_SAMPLES = 6
CALIBRATION_ENDPOINT_TIMEOUT_SECONDS = 50.0
CALIBRATION_RESTORE_TIMEOUT_SECONDS = 40.0

# Native absolute moves are commanded in whole millimetres while position feedback
# arrives in tenths of an inch. On hardware, a requested percentage can therefore
# legitimately settle one 1%-slider step away from the rounded tenths-inch target.
# Treat +/-0.2 in (2 raw units) as reached once that position is stable.
ABSOLUTE_POSITION_TOLERANCE_RAW = 2
ABSOLUTE_POSITION_STABLE_SECONDS = 0.5

# Preset programming is timing-sensitive immediately after motion. Before the
# mutating SAVE_PRESET write, obtain several fresh identical position samples via
# the read-only 0x07 query so the controller has demonstrably settled.
PRESET_SAVE_STABLE_SAMPLES = 5
PRESET_SAVE_SAMPLE_INTERVAL_SECONDS = 0.20
PRESET_SAVE_SETTLE_TIMEOUT_SECONDS = 4.0

_KNOWN_RX_COMMANDS = {
    POSITION_RESPONSE,
    ERROR_RESPONSE,
    RST_RESPONSE,
    LOCK_RESPONSE,
    LIMIT_FLAGS_RESPONSE,
    MAX_LIMIT_RESPONSE,
    MIN_LIMIT_RESPONSE,
    *PRESET_RESPONSE.keys(),
}


@dataclass
class ActuatorState:
    """Latest decoded state from the Bluetooth actuator controller."""

    position: int | None = None
    status_byte: int | None = None
    lower_limit: int | None = None
    upper_limit: int | None = None
    physical_min: int | None = None
    physical_max: int | None = None
    limit_flags: int | None = None
    locked: bool | None = None
    error_code: int | None = None
    presets: dict[int, int] = field(default_factory=dict)
    target_extension_inches: float | None = None
    protocol_variant: str | None = None
    connected: bool = False
    activity: str = "idle"
    last_error: str | None = None

    @property
    def extension_inches(self) -> float | None:
        if self.position is None:
            return None
        return self.position / 10.0

    @property
    def position_percent(self) -> float | None:
        """Return 0..100% across the calibrated physical travel span."""
        if (
            self.position is None
            or self.physical_min is None
            or self.physical_max is None
            or self.physical_max <= self.physical_min
        ):
            return None

        span = self.physical_max - self.physical_min
        return max(
            0.0,
            min(100.0, ((self.position - self.physical_min) / span) * 100.0),
        )

    @property
    def target_position_percent(self) -> float | None:
        """Return the current absolute-move target as 0..100%, when available."""
        if (
            self.target_extension_inches is None
            or self.physical_min is None
            or self.physical_max is None
            or self.physical_max <= self.physical_min
        ):
            return None

        target_raw = self.target_extension_inches * 10.0
        span = self.physical_max - self.physical_min
        return max(
            0.0,
            min(100.0, ((target_raw - self.physical_min) / span) * 100.0),
        )


class RTBT1Controller:
    """Manage a reusable BLE session to a Progressive Automations RT-BT1."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, address: str) -> None:
        self.hass = hass
        self.entry = entry
        self.address = address.upper()
        self.name = f"RT-BT1 {self.address[-8:]}"
        self.state = ActuatorState()

        # Learned physical travel belongs to the physical RT-BT1 installation,
        # not to a transient Home Assistant config-entry identifier. Key the
        # durable store to the normalized Bluetooth address so calibration
        # survives an entry being recreated during an update/reinstall. Keep the
        # rc40/rc41 entry-keyed store as a one-way migration source.
        storage_device_id = "".join(
            ch for ch in self.address.lower() if ch.isalnum()
        )
        self._calibration_store: Store[dict[str, int]] = Store(
            hass,
            1,
            f"{DOMAIN}.calibration.device.{storage_device_id}",
        )
        self._legacy_calibration_store: Store[dict[str, int]] = Store(
            hass,
            1,
            f"{DOMAIN}.calibration.{entry.entry_id}",
        )

        self._listeners: set[Listener] = set()
        self._session_lock = asyncio.Lock()
        self._replace_lock = asyncio.Lock()
        self._tx_lock = asyncio.Lock()

        # Lock/unlock is a short serialized transaction. Keep the transition
        # state explicit instead of using a detached worker task; this guarantees
        # entities are notified both when a transition starts and when it ends.
        self._lock_operation_lock = asyncio.Lock()
        self._lock_transition_target: bool | None = None

        self._client: BleakClientWithServiceCache | None = None
        self._write_uuid = V2_WRITE_UUID
        self._notify_uuid = V2_NOTIFY_UUID
        self._rx = bytearray()
        self._position_event = asyncio.Event()
        self._lock_event = asyncio.Event()
        self._rst_event = asyncio.Event()
        self._position_rx_count = 0
        self._limit_flags_rx_count = 0
        self._upper_limit_rx_count = 0
        self._lower_limit_rx_count = 0

        self._motion_task: asyncio.Task[None] | None = None
        self._rehome_active = False
        self._calibration_active = False
        self._travel_limit_active = False
        self._idle_task: asyncio.Task[None] | None = None
        self._stop_requested = asyncio.Event()

        self._last_tx_at = 0.0

        # Passive diagnostics counters. These intentionally do not participate
        # in motion, wake, retry, or connection decisions. All counters are
        # scoped to this integration load (they intentionally reset on reload).
        self.diag_session_started_at_utc = datetime.now(timezone.utc)
        self.diag_last_successful_communication_at_utc: datetime | None = None
        self.diag_last_error_message: str | None = None
        self.diag_last_error_at_utc: datetime | None = None
        self.diag_fe61_writes = 0
        self.diag_fe62_frames = 0
        self.diag_fe62_checksum_errors = 0
        self.diag_fe62_parse_errors = 0
        self.diag_fe62_recovered_frames = 0
        self.diag_ble_sessions = 0
        self.diag_last_fe62_at: float | None = None
        self.diag_last_parse_error_reason: str | None = None
        self.diag_last_parse_error_payload: str | None = None
        self.diag_last_parse_error_at: float | None = None
        self.diag_last_recovery_reason: str | None = None
        self.diag_last_recovery_payload: str | None = None
        self.diag_last_recovery_at: float | None = None
        self.diag_last_limit_status_at: float | None = None
        self.diag_last_travel_limit_snapshot_at: float | None = None
        self.diag_last_travel_limit_snapshot_at_utc: datetime | None = None
        self.diag_last_travel_limit_snapshot_lower: int | None = None
        self.diag_last_travel_limit_snapshot_upper: int | None = None
        # Travel-limit reset diagnostics distinguish a user request from the
        # single mutating 0x23 write and its later read-only verification.
        self.diag_reset_requests = 0
        # A "write" counter means the host-side GATT write call completed. The
        # RT-BT1 protocol does not provide a direct acknowledgement for 0x23, so
        # controller acceptance is established only by later status readback.
        self.diag_reset_writes = 0
        self.diag_reset_preflight_queries = 0
        self.diag_reset_preflight_confirmed = 0
        self.diag_reset_verification_queries = 0
        self.diag_reset_verified_clears = 0
        self.diag_last_reset_result: str | None = None

        # General BLE command observability. These counters are deliberately
        # passive: they describe what this integration attempted/completed and
        # what valid protocol frames it received, but never affect retry or
        # controller behavior. This provides an authoritative integration-side
        # command trail that is independent of Home Assistant ButtonEntity
        # restore/logbook timestamps.
        self.diag_gatt_write_attempts = 0
        self.diag_gatt_write_failures = 0
        self.diag_gatt_write_counts: dict[str, int] = {}
        self.diag_last_gatt_write_name: str | None = None
        self.diag_last_gatt_write_opcode: int | None = None
        self.diag_last_gatt_write_payload: str | None = None
        self.diag_last_gatt_write_at: float | None = None
        self.diag_last_gatt_write_result: str | None = None
        # Last non-query command is kept separately so user-facing diagnostics
        # do not get overwritten by routine read-only synchronization traffic.
        self.diag_last_command_name: str | None = None
        self.diag_last_command_opcode: int | None = None
        self.diag_last_command_payload: str | None = None
        self.diag_last_command_at: float | None = None
        self.diag_last_command_result: str | None = None

        self.diag_rx_command_counts: dict[str, int] = {}
        self.diag_last_rx_name: str | None = None
        self.diag_last_rx_opcode: int | None = None
        self.diag_last_rx_payload: str | None = None
        self.diag_last_rx_at: float | None = None

        # High-level maintenance-operation counters/results. These answer the
        # important question "did the integration actually request this?"
        # without relying on Home Assistant's restored button timestamps.
        self.diag_rst_requests = 0
        self.diag_rst_completed = 0
        self.diag_rst_failures = 0
        self.diag_rst_response_frames = 0
        self.diag_last_rst_result: str | None = None

        self.diag_calibration_requests = 0
        self.diag_calibration_completed = 0
        self.diag_calibration_failures = 0
        self.diag_calibration_stopped = 0
        self.diag_last_calibration_result: str | None = None

        self.diag_lower_limit_requests = 0
        self.diag_lower_limit_writes = 0
        self.diag_lower_limit_verified = 0
        self.diag_last_lower_limit_result: str | None = None
        self.diag_upper_limit_requests = 0
        self.diag_upper_limit_writes = 0
        self.diag_upper_limit_verified = 0
        self.diag_last_upper_limit_result: str | None = None

        self.diag_activity_transitions = 0
        self.diag_previous_activity: str | None = None
        self.diag_activity_changed_at: float | None = None

        # One-shot preset programming mode. When armed, the next Preset 1-4 press
        # saves the current position into that slot instead of moving to it.
        # It automatically disarms after 10 seconds or immediately after use.
        self.program_preset_mode = False
        self._program_preset_timeout_task: asyncio.Task[None] | None = None


    @property
    def controls_inhibited(self) -> bool:
        """Return whether ordinary actuator-changing controls should be blocked.

        Every ordinary actuator-changing control requires a positively confirmed
        Unlocked state. RST re-home is a dedicated recovery state machine and
        temporarily blocks every ordinary motion/configuration control regardless
        of lock state so nothing can interrupt the sequence.
        """
        return (
            self._rehome_active
            or self._calibration_active
            or self._travel_limit_active
            or self.state.locked is not False
            or self._lock_transition_target is not None
        )

    @property
    def autonomous_controls_inhibited(self) -> bool:
        """Return whether autonomous/stateful actuator actions are blocked."""
        return self.controls_inhibited

    @property
    def stop_inhibited(self) -> bool:
        """Return whether explicit 0x2B STOP must be blocked.

        Hardware testing showed that sending 0x2B while the RT-BT1 is locked can
        leave the controller in a persistent control-inhibited state. STOP is also
        deliberately suppressed throughout RST re-home: Progressive Motion performs
        that sequence only by starting/stopping repeated DOWN writes.
        """
        return (
            self._rehome_active
            or self._travel_limit_active
            or self.state.locked is not False
            or self._lock_transition_target is not None
        )

    @property
    def rehome_active(self) -> bool:
        """Return whether the dedicated RST re-home state machine is running."""
        return self._rehome_active

    @property
    def calibration_active(self) -> bool:
        """Return whether physical position-range calibration is running."""
        return self._calibration_active

    @property
    def travel_limit_active(self) -> bool:
        """Return whether a travel-limit configuration transaction is running."""
        return self._travel_limit_active

    @property
    def calibration_state(self) -> str:
        """Return required/calibrating/calibrated for the Position Calibration entity."""
        if self._calibration_active:
            return "calibrating"
        if (
            self.state.physical_min is not None
            and self.state.physical_max is not None
            and self.state.physical_max > self.state.physical_min
        ):
            return "calibrated"
        return "required"

    @property
    def motion_active(self) -> bool:
        """Return whether Home Assistant currently owns an actuator motion task."""
        task = self._motion_task
        return task is not None and not task.done()

    @property
    def lock_transition_target(self) -> bool | None:
        """Return the requested lock state while a lock transaction is active."""
        return self._lock_transition_target

    def _assert_controls_unlocked(self) -> None:
        """Require a positively confirmed Unlocked state for actuator commands."""
        if self._rehome_active:
            raise RuntimeError("RST re-home is in progress")
        if self._calibration_active:
            raise RuntimeError("Position calibration is in progress")
        if self._travel_limit_active:
            raise RuntimeError("Travel-limit configuration is in progress")
        if self.controls_inhibited:
            if self.state.locked is None:
                raise RuntimeError(
                    "Control-lock state is unknown; wait for controller lock-state "
                    "synchronization and retry"
                )
            raise RuntimeError("Actuator controls are currently locked")

    def _assert_confirmed_unlocked(self) -> None:
        """Require a positively known Unlocked state for autonomous actions."""
        if self._rehome_active:
            raise RuntimeError("RST re-home is in progress")
        if self._calibration_active:
            raise RuntimeError("Position calibration is in progress")
        if self._travel_limit_active:
            raise RuntimeError("Travel-limit configuration is in progress")
        if self.autonomous_controls_inhibited:
            if self.state.locked is None:
                raise RuntimeError(
                    "Control-lock state is unknown; wait for controller lock-state "
                    "synchronization and retry"
                )
            raise RuntimeError("Actuator controls are currently locked")

    def add_listener(self, listener: Listener) -> Callable[[], None]:
        self._listeners.add(listener)

        def remove() -> None:
            self._listeners.discard(listener)

        return remove

    def _notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Progressive Automations listener failed")

    def _set_error(self, message: str | None) -> None:
        self.state.last_error = message
        if message is not None:
            self.diag_last_error_message = message
            self.diag_last_error_at_utc = datetime.now(timezone.utc)
        self._notify_listeners()

    def _set_activity(self, activity: str) -> None:
        if self.state.activity != activity:
            self.diag_previous_activity = self.state.activity
            self.state.activity = activity
            self.diag_activity_transitions += 1
            self.diag_activity_changed_at = monotonic()
            self._notify_listeners()

    def _cancel_idle_disconnect(self) -> None:
        task = self._idle_task
        self._idle_task = None
        if task is not None and not task.done():
            task.cancel()

    def _schedule_idle_disconnect(self) -> None:
        self._cancel_idle_disconnect()
        self._idle_task = self.hass.async_create_task(
            self._idle_disconnect_after_delay()
        )

    async def _idle_disconnect_after_delay(self) -> None:
        try:
            await asyncio.sleep(IDLE_DISCONNECT_SECONDS)
            task = self._motion_task
            if task is None or task.done():
                await self._disconnect_session()
        except asyncio.CancelledError:
            pass

    async def _find_device(self) -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

        if device is None:
            try:
                await bluetooth.async_request_active_scan(self.hass, duration=5.0)
            except Exception:
                _LOGGER.debug("Active scan request failed", exc_info=True)

            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )

        if device is None:
            reason = bluetooth.async_address_reachability_diagnostics(
                self.hass,
                self.address,
                bluetooth.BluetoothReachabilityIntent.CONNECTION,
            )
            raise RuntimeError(f"RT-BT1 not reachable: {reason}")

        return device

    def _select_protocol(self, client: BleakClientWithServiceCache) -> None:
        """Select the vendor GATT layout exposed by the connected controller."""
        services = client.services

        if (
            services.get_service(V2_SERVICE_UUID) is not None
            and services.get_characteristic(V2_WRITE_UUID) is not None
            and services.get_characteristic(V2_NOTIFY_UUID) is not None
        ):
            self._write_uuid = V2_WRITE_UUID
            self._notify_uuid = V2_NOTIFY_UUID
            self.state.protocol_variant = "V2"
            return

        if (
            services.get_service(V1_SERVICE_UUID) is not None
            and services.get_characteristic(V1_WRITE_UUID) is not None
            and services.get_characteristic(V1_NOTIFY_UUID) is not None
        ):
            self._write_uuid = V1_WRITE_UUID
            self._notify_uuid = V1_NOTIFY_UUID
            self.state.protocol_variant = "V1"
            return

        raise RuntimeError(
            "Connected Bluetooth device does not expose a supported "
            "Progressive Automations GATT service"
        )

    async def _ensure_session(self) -> BleakClientWithServiceCache:
        """Return a live client, opening and initializing one when necessary."""
        self._cancel_idle_disconnect()

        async with self._session_lock:
            client = self._client
            if client is not None and client.is_connected:
                return client

            self._client = None

            # Never carry a lock state across BLE sessions. The physical lock
            # persists across disconnects and can be changed by Progressive Motion
            # while Home Assistant is offline, so a reconnect must begin Unknown
            # until the controller answers LOCK_QUERY.
            self.state.locked = None
            self._lock_event.clear()
            self._set_activity("connecting")
            device = await self._find_device()

            self._rx.clear()
            self._position_event.clear()
            self._rst_event.clear()

            client = await establish_connection(
                BleakClientWithServiceCache,
                device,
                self.name,
                max_attempts=4,
            )

            try:
                self._select_protocol(client)
            except Exception:
                try:
                    await client.disconnect()
                except Exception:
                    pass
                raise

            self._client = client
            self.diag_ble_sessions += 1
            self.state.connected = True
            self.state.last_error = None
            self._notify_listeners()

            await client.start_notify(self._notify_uuid, self._notification_handler)

            # Reproduce Progressive Motion's captured startup cadence while using
            # the now-proven semantics of 1F/00: it is a read-only lock-state query.
            # Some cold sessions do not answer the first query immediately, so the
            # normal 0x07/0x20 initialization burst primes the protocol and we retry
            # the same non-mutating query once if needed.
            self._lock_event.clear()
            await self._write(client, LOCK_QUERY)
            await asyncio.sleep(0.060)
            await self._write(client, QUERY_LIMITS)
            await asyncio.sleep(0.060)
            await self._write(client, QUERY_STATUS)

            try:
                await asyncio.wait_for(self._position_event.wait(), timeout=1.5)
            except TimeoutError:
                _LOGGER.debug("No position frame received during startup burst")

            await asyncio.sleep(0.20)

            if self.state.locked is None:
                await self._query_lock_state(client, timeout=0.75)

            if self.state.upper_limit is None or self.state.lower_limit is None:
                await self._write(client, QUERY_LIMITS)
                await asyncio.sleep(0.20)

            if self.state.locked is None:
                _LOGGER.warning(
                    "RT-BT1 did not report control-lock state during session startup"
                )

            return client

    async def _disconnect_session(self) -> None:
        async with self._session_lock:
            client = self._client
            self._client = None

            if client is not None:
                try:
                    if client.is_connected:
                        try:
                            await client.stop_notify(self._notify_uuid)
                        except Exception:
                            _LOGGER.debug("stop_notify failed", exc_info=True)
                        await client.disconnect()
                except Exception:
                    _LOGGER.debug("BLE disconnect failed", exc_info=True)

            self.state.connected = False
            # Keep the last confirmed lock value visible while intentionally idle.
            # The next BLE session always resets it to Unknown before querying the
            # physical controller, so no state-changing command can rely on a stale
            # value after another client has used the RT-BT1.
            self._lock_event.clear()
            if self.state.activity == "connected":
                self.state.activity = "idle"
            self._notify_listeners()

    async def _query_lock_state(
        self,
        client: BleakClientWithServiceCache,
        *,
        timeout: float = 0.75,
    ) -> bool:
        """Request the current physical lock state without mutating it.

        Differential hardware tests prove LOCK_QUERY returns an authoritative
        0x1F response with payload 00 for Unlocked and 01 for Locked. The event is
        set even when the reported state equals the previous state, so this method
        can distinguish a fresh confirmation from a stale cached value.
        """
        self._lock_event.clear()
        await self._write(client, LOCK_QUERY)
        try:
            await asyncio.wait_for(self._lock_event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    async def _synchronize_lock_state_for_toggle(
        self,
        client: BleakClientWithServiceCache,
        *,
        attempts: int = 2,
        timeout: float = 0.90,
    ) -> bool:
        """Run the captured non-mutating control-session sync before a toggle.

        Hardware testing showed rc32's extra *standalone* LOCK_QUERY could be
        ignored even though the immediately preceding session-start burst had
        successfully reported lock state. The reliable pattern is the native
        startup cadence: LOCK_QUERY -> 60 ms -> QUERY_LIMITS -> 60 ms ->
        QUERY_STATUS. All three commands are read/status operations.

        Repeating this burst is safe because it contains no state-changing
        command. A lock toggle is still forbidden unless a fresh 0x1F response
        is observed from this synchronization transaction.
        """
        for attempt in range(max(1, attempts)):
            # The 0x1F lock response can arrive before the 0x07/0x20 response
            # burst has finished. rc33 returned as soon as _lock_event was set,
            # which could place LOCK_TOGGLE into the middle of that still-active
            # response burst. Hardware testing then showed the controller could
            # ignore the toggle. Mirror the proven startup path instead: require
            # both a fresh lock response and a fresh position response, then give
            # the tail of the read/status burst the same 200 ms settling window
            # used during normal session startup before any state-changing write.
            self._lock_event.clear()
            self._position_event.clear()
            await self._write(client, LOCK_QUERY)
            await asyncio.sleep(0.060)
            await self._write(client, QUERY_LIMITS)
            await asyncio.sleep(0.060)
            await self._write(client, QUERY_STATUS)

            try:
                await asyncio.wait_for(self._lock_event.wait(), timeout=timeout)
                await asyncio.wait_for(self._position_event.wait(), timeout=timeout)
                await asyncio.sleep(0.20)
                return True
            except TimeoutError:
                if attempt + 1 < max(1, attempts):
                    await asyncio.sleep(0.20)

        return False

    @staticmethod
    def _describe_tx(payload: bytes) -> tuple[str, int | None]:
        """Return a stable diagnostic label for one outbound protocol frame."""
        if len(payload) < 3 or payload[:2] != b"\xF1\xF1":
            return "unknown", None
        opcode = payload[2]
        names = {
            0x01: "extend",
            0x02: "retract",
            0x03: "save_preset_1",
            0x04: "save_preset_2",
            0x05: "move_preset_1",
            0x06: "move_preset_2",
            0x07: "query_position_presets",
            0x0A: "momentary_release",
            0x1B: "move_absolute",
            0x20: "query_status_travel_limits",
            0x21: "save_upper_travel_limit",
            0x22: "save_lower_travel_limit",
            0x23: "reset_travel_limits",
            0x25: "save_preset_3",
            0x26: "save_preset_4",
            0x27: "move_preset_3",
            0x28: "move_preset_4",
            0x2B: "stop",
        }
        if opcode == 0x1F:
            if len(payload) >= 6 and payload[4] == 0x00:
                return "query_control_lock", opcode
            if len(payload) >= 6 and payload[4] == 0x01:
                return "toggle_control_lock", opcode
            return "control_lock_0x1f", opcode
        return names.get(opcode, f"opcode_0x{opcode:02X}"), opcode

    @staticmethod
    def _describe_rx(command: int) -> str:
        names = {
            POSITION_RESPONSE: "position",
            ERROR_RESPONSE: "controller_error",
            RST_RESPONSE: "rst_state",
            LOCK_RESPONSE: "control_lock_state",
            LIMIT_FLAGS_RESPONSE: "travel_limit_flags",
            MAX_LIMIT_RESPONSE: "upper_travel_limit",
            MIN_LIMIT_RESPONSE: "lower_travel_limit",
            0x25: "preset_1",
            0x26: "preset_2",
            0x27: "preset_3",
            0x28: "preset_4",
        }
        return names.get(command, f"opcode_0x{command:02X}")

    async def _write(
        self, client: BleakClientWithServiceCache, payload: bytes
    ) -> None:
        async with self._tx_lock:
            name, opcode = self._describe_tx(payload)
            payload_hex = payload.hex(" ").upper()
            self.diag_gatt_write_attempts += 1
            self.diag_last_gatt_write_name = name
            self.diag_last_gatt_write_opcode = opcode
            self.diag_last_gatt_write_payload = payload_hex
            self.diag_last_gatt_write_at = monotonic()
            self.diag_last_gatt_write_result = "attempting"
            is_action_command = not name.startswith("query_")
            if is_action_command:
                self.diag_last_command_name = name
                self.diag_last_command_opcode = opcode
                self.diag_last_command_payload = payload_hex
                self.diag_last_command_at = self.diag_last_gatt_write_at
                self.diag_last_command_result = "attempting"
            _LOGGER.debug("BLE TX (%s): %s", self._write_uuid, payload_hex)
            try:
                await client.write_gatt_char(self._write_uuid, payload, response=False)
            except Exception:
                self.diag_gatt_write_failures += 1
                self.diag_last_gatt_write_result = "failed"
                if is_action_command:
                    self.diag_last_command_result = "failed"
                raise
            self.diag_fe61_writes += 1
            self.diag_gatt_write_counts[name] = self.diag_gatt_write_counts.get(name, 0) + 1
            self.diag_last_gatt_write_result = "completed"
            if is_action_command:
                self.diag_last_command_result = "completed"
            self._last_tx_at = monotonic()

    async def _prepare_motion_session(self) -> BleakClientWithServiceCache:
        """Prepare a clean motion session.

        Lock/unlock is deliberately isolated. If a lock transaction is still in
        flight, this movement press is rejected rather than queued to run later.
        """
        if self._lock_transition_target is not None:
            raise RuntimeError(
                "Lock transition in progress; movement was not queued"
            )

        if self.state.locked is not False:
            raise RuntimeError("Actuator controls are not confirmed unlocked")

        client = await self._ensure_session()

        if self.state.locked is not False:
            raise RuntimeError("Actuator controls are not confirmed unlocked")

        if monotonic() - self._last_tx_at > WAKE_AFTER_SECONDS:
            # 0x07 is a real limit/state read and also reliably wakes the box.
            await self._write(client, QUERY_LIMITS)
            await asyncio.sleep(WAKE_SETTLE_SECONDS)

        return client

    def _notification_handler(self, _sender, data: bytearray) -> None:
        self._rx.extend(data)
        self._parse_rx_buffer()

    def _try_single_f2_frame(self) -> bool:
        """Recover the one-byte-missing F2 header pattern seen in limit dumps."""
        for start in range(max(0, len(self._rx) - 64), len(self._rx) - 4):
            if self._rx[start] != 0xF2:
                continue

            command = self._rx[start + 1]
            if command not in _KNOWN_RX_COMMANDS:
                continue

            payload_len = self._rx[start + 2]
            total_len = 5 + payload_len
            if start + total_len > len(self._rx):
                continue

            end = start + total_len
            frame = bytes(self._rx[start:end])
            if frame[-1] != 0x7E:
                continue

            checksum_index = 3 + payload_len
            expected = sum(frame[1:checksum_index]) & 0xFF
            if frame[checksum_index] != expected:
                continue

            del self._rx[:end]
            params = frame[3:checksum_index]
            _LOGGER.debug(
                "FE62 RX recovered single-header frame: F2 %s",
                frame[1:].hex(" ").upper(),
            )
            self.diag_fe62_frames += 1
            self.diag_fe62_recovered_frames += 1
            self.diag_last_fe62_at = monotonic()
            self.diag_last_recovery_reason = "single_header_recovery"
            self.diag_last_recovery_payload = (b"\xF2" + frame).hex(" ").upper()
            self.diag_last_recovery_at = self.diag_last_fe62_at
            self._handle_frame(command, params)
            return True

        return False

    def _parse_rx_buffer(self) -> None:
        while True:
            start = self._rx.find(b"\xF2\xF2")

            if start < 0:
                if self._try_single_f2_frame():
                    continue

                if self._rx[-1:] == b"\xF2":
                    self._rx[:] = b"\xF2"
                elif len(self._rx) > 64:
                    self._rx.clear()
                return

            if start:
                if self._try_single_f2_frame():
                    continue
                del self._rx[:start]

            if len(self._rx) < 4:
                return

            payload_len = self._rx[3]
            total_len = 6 + payload_len
            if len(self._rx) < total_len:
                return

            frame = bytes(self._rx[:total_len])
            if frame[-1] != 0x7E:
                self.diag_fe62_parse_errors += 1
                self.diag_last_parse_error_reason = "missing_frame_terminator"
                self.diag_last_parse_error_payload = frame.hex(" ").upper()
                self.diag_last_parse_error_at = monotonic()
                del self._rx[0]
                continue

            checksum_index = 4 + payload_len
            expected = sum(frame[2:checksum_index]) & 0xFF
            if frame[checksum_index] != expected:
                self.diag_fe62_checksum_errors += 1
                self.diag_fe62_parse_errors += 1
                self.diag_last_parse_error_reason = "checksum_mismatch"
                self.diag_last_parse_error_payload = frame.hex(" ").upper()
                self.diag_last_parse_error_at = monotonic()
                _LOGGER.debug(
                    "Ignoring FE62 frame with bad checksum: %s",
                    frame.hex(" ").upper(),
                )
                del self._rx[0]
                continue

            del self._rx[:total_len]
            command = frame[2]
            params = frame[4:checksum_index]
            _LOGGER.debug("FE62 RX: %s", frame.hex(" ").upper())
            self.diag_fe62_frames += 1
            self.diag_last_fe62_at = monotonic()
            self._handle_frame(command, params)

    @staticmethod
    def _u16_be(params: bytes) -> int:
        return (params[0] << 8) | params[1]

    def _handle_frame(self, command: int, params: bytes) -> None:
        changed = False
        self.diag_last_successful_communication_at_utc = datetime.now(timezone.utc)
        rx_name = self._describe_rx(command)
        self.diag_rx_command_counts[rx_name] = self.diag_rx_command_counts.get(rx_name, 0) + 1
        self.diag_last_rx_name = rx_name
        self.diag_last_rx_opcode = command
        self.diag_last_rx_payload = params.hex(" ").upper()
        self.diag_last_rx_at = monotonic()

        if command == POSITION_RESPONSE and len(params) >= 3:
            # Standard response: F2 F2 01 03 00 POS STATUS CHECKSUM 7E.
            # Treat the first two payload bytes as big-endian for forward
            # compatibility; current RT-BT1 hardware reports a zero high byte.
            position = self._u16_be(params)
            if position != self.state.position:
                self.state.position = position
                changed = True

            if params[2] != self.state.status_byte:
                self.state.status_byte = params[2]
                changed = True
            self._position_rx_count += 1
            self._position_event.set()

        elif command == RST_RESPONSE and len(params) == 0:
            self.diag_rst_response_frames += 1
            # Hardware-proven FLTCON-1 RST state:
            # F2 F2 04 00 04 7E. This is a synchronization event for the
            # dedicated re-home state machine, not a persistent controller error.
            self._rst_event.set()

        elif command == ERROR_RESPONSE and len(params) >= 1:
            code = params[0]
            if self.state.error_code != code:
                self.state.error_code = code
                changed = True
            message = f"Controller error code {code}"
            if self.state.last_error != message:
                self.state.last_error = message
                changed = True
            self.diag_last_error_message = message
            self.diag_last_error_at_utc = datetime.now(timezone.utc)

        elif command == LOCK_RESPONSE and len(params) >= 1:
            state_byte = params[0]
            if state_byte not in (0, 1):
                _LOGGER.debug(
                    "Ignoring FE62 lock-state response with invalid payload: %s",
                    params.hex(" ").upper(),
                )
                return

            locked = state_byte == 1
            if self.state.locked != locked:
                self.state.locked = locked
                changed = True

            # If another client locked the controller while HA was idle, never
            # leave one-shot preset programming armed from the previous session.
            if locked and self.program_preset_mode:
                self._cancel_program_preset_timeout()
                self.program_preset_mode = False
                changed = True

            self._lock_event.set()

        elif command in PRESET_RESPONSE and len(params) >= 2:
            preset = PRESET_RESPONSE[command]
            value = self._u16_be(params)
            if self.state.presets.get(preset) != value:
                self.state.presets[preset] = value
                changed = True

        elif command == LIMIT_FLAGS_RESPONSE and len(params) >= 1:
            self._limit_flags_rx_count += 1
            self.diag_last_limit_status_at = monotonic()
            if self.state.limit_flags != params[0]:
                self.state.limit_flags = params[0]
                changed = True

        elif command == MAX_LIMIT_RESPONSE and len(params) >= 2:
            self._upper_limit_rx_count += 1
            value = self._u16_be(params)
            if self.state.upper_limit != value:
                self.state.upper_limit = value
                changed = True

        elif command == MIN_LIMIT_RESPONSE and len(params) >= 2:
            self._lower_limit_rx_count += 1
            value = self._u16_be(params)
            if self.state.lower_limit != value:
                self.state.lower_limit = value
                changed = True

        if changed:
            self._notify_listeners()

    async def async_refresh(self) -> None:
        """Explicitly refresh lock, position, limits, and aggregate state."""
        try:
            client = await self._ensure_session()
            self._set_activity("refreshing")

            lock_confirmed = await self._query_lock_state(client, timeout=0.60)
            await self._write(client, QUERY_LIMITS)
            await asyncio.sleep(0.060)
            await self._write(client, QUERY_STATUS)
            await asyncio.sleep(0.40)

            if self.state.upper_limit is None or self.state.lower_limit is None:
                await self._write(client, QUERY_LIMITS)
                await asyncio.sleep(0.25)

            if not lock_confirmed and self.state.locked is None:
                # One final read-only retry after the normal status traffic has
                # primed the controller. Never substitute motion or a toggle as a
                # lock-state probe.
                lock_confirmed = await self._query_lock_state(client, timeout=0.75)

            if lock_confirmed or self.state.locked is not None:
                self._set_error(None)
            else:
                self._set_error("RT-BT1 did not report control-lock state")
        except Exception as err:
            _LOGGER.exception("Unable to refresh RT-BT1")
            self._set_error(str(err))
            await self._disconnect_session()
        finally:
            self._set_activity("idle")
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def _run_jog(
        self,
        upward: bool,
        seconds: float = MOMENTARY_DURATION_SECONDS,
    ) -> None:
        """MOM behavior with an accurately bounded short press.

        The vendor app repeats direction packets about every 200 ms while a MOM
        button is held, then sends 0x0A on release. For the default 125 ms tap
        this produces a single direction write at roughly t=0, followed by
        MOM_RELEASE at roughly t=125 ms instead of overshooting to ~400 ms.
        """
        client = None
        try:
            client = await self._prepare_motion_session()
            command = RAISE if upward else LOWER
            self._set_activity("extending_momentary" if upward else "retracting_momentary")

            started = monotonic()
            next_send = started

            while not self._stop_requested.is_set():
                now = monotonic()
                elapsed = now - started
                remaining = seconds - elapsed

                if remaining <= 0:
                    break

                if now >= next_send:
                    await self._write(client, command)
                    next_send += REPEAT_INTERVAL_SECONDS

                sleep_for = min(
                    max(0.0, next_send - monotonic()),
                    max(0.0, seconds - (monotonic() - started)),
                )
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)

            if self._stop_requested.is_set():
                # 0x2B STOP is unsafe unless Unlocked is positively known. If a
                # first/Unknown-state jog is superseded before motion feedback
                # proves Unlocked, fall back to the vendor's normal 0x0A
                # momentary-release frame rather than leaving the jog asserted.
                sent_stop = await self._write_stop_if_safe(client)
                if not sent_stop:
                    await self._write(client, MOM_RELEASE)
            else:
                await self._write(client, MOM_RELEASE)

            await asyncio.sleep(0.08)
            self._set_error(None)

        except Exception as err:
            _LOGGER.exception("RT-BT1 momentary jog failed")
            self._set_error(str(err))
            if client is not None and client.is_connected:
                try:
                    await self._write_stop_if_safe(client)
                except Exception:
                    pass
            await self._disconnect_session()

        finally:
            self._set_activity("idle")
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def _run_to_endpoint(self, upward: bool, activity: str) -> None:
        """Repeat direction until STOP or the physical endpoint settles."""
        client = None
        try:
            client = await self._prepare_motion_session()
            command = RAISE if upward else LOWER
            self._set_activity(activity)

            # Endpoint detection relies on position feedback. If the controller
            # never reported one, poke it once and fail fast instead of grinding
            # the actuator for the full timeout on a silent link.
            if self.state.position is None:
                self._position_event.clear()
                await self._write(client, QUERY_STATUS)
                try:
                    await asyncio.wait_for(self._position_event.wait(), timeout=1.0)
                except TimeoutError:
                    pass

            if self.state.position is None:
                raise RuntimeError(
                    "No position feedback from RT-BT1; cannot detect endpoint"
                )

            deadline = monotonic() + ENDPOINT_TIMEOUT_SECONDS
            last_position = self.state.position
            last_change_at = monotonic()

            while monotonic() < deadline:
                if self._stop_requested.is_set():
                    await self._write_stop_if_safe(client)
                    break

                await self._write(client, command)
                await asyncio.sleep(REPEAT_INTERVAL_SECONDS)

                position = self.state.position
                if position is not None and position != last_position:
                    last_position = position
                    last_change_at = monotonic()
                elif (
                    position is not None
                    and monotonic() - last_change_at >= ENDPOINT_STABLE_SECONDS
                ):
                    # This reproduces the vendor app's ON/OFF endpoint behavior:
                    # it repeats UP/DOWN, sees the position stop changing, then sends 2B.
                    await self._write_stop_if_safe(client)
                    break
            else:
                await self._write_stop_if_safe(client)

            self._set_error(None)

        except Exception as err:
            _LOGGER.exception("RT-BT1 endpoint motion failed")
            self._set_error(str(err))
            if client is not None and client.is_connected:
                try:
                    await self._write_stop_if_safe(client)
                except Exception:
                    pass
            await self._disconnect_session()

        finally:
            self._set_activity("idle")
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def _run_preset(self, preset: int) -> None:
        """Send an autonomous memory move and monitor FE62 until it settles."""
        if preset not in MOVE_PRESET:
            raise ValueError(f"Invalid preset {preset}")

        client = None
        try:
            client = await self._prepare_motion_session()

            target = self.state.presets.get(preset)
            if target is None:
                # Preset readback normally arrives during the startup settings
                # burst. Retry the two non-mutating state requests before falling
                # back to generic stable-position completion detection.
                await self._write(client, QUERY_LIMITS)
                await asyncio.sleep(0.060)
                await self._write(client, QUERY_STATUS)
                await asyncio.sleep(0.35)
                target = self.state.presets.get(preset)

            if self.state.position is None:
                self._position_event.clear()
                await self._write(client, QUERY_STATUS)
                try:
                    await asyncio.wait_for(self._position_event.wait(), timeout=1.0)
                except TimeoutError:
                    pass

            if self.state.position is None:
                raise RuntimeError(
                    "No position feedback from controller; cannot monitor preset move"
                )

            self._set_activity(f"preset_{preset}")
            await self._write(client, MOVE_PRESET[preset])

            deadline = monotonic() + 40.0
            started = monotonic()
            last_position = self.state.position
            last_change_at = started
            motion_started = False
            at_target_since: float | None = None

            while monotonic() < deadline:
                if self._stop_requested.is_set():
                    await self._write_stop_if_safe(client)
                    break

                now = monotonic()
                position = self.state.position

                if target is not None and position is not None and abs(position - target) <= 1:
                    if at_target_since is None:
                        at_target_since = now
                    elif now - at_target_since >= 0.6:
                        break
                else:
                    at_target_since = None

                if position is not None and position != last_position:
                    last_position = position
                    last_change_at = now
                    motion_started = True
                elif (
                    target is None
                    and motion_started
                    and now - last_change_at >= ENDPOINT_STABLE_SECONDS
                ):
                    break

                # If a preset is already at the current position, no movement is
                # expected. Two seconds is enough to distinguish that from startup.
                if not motion_started and now - started >= 2.0:
                    if target is None or (position is not None and abs(position - target) <= 1):
                        break

                await asyncio.sleep(0.1)
            else:
                await self._write_stop_if_safe(client)
                raise RuntimeError("Preset movement timed out")

            self._set_error(None)

        except Exception as err:
            _LOGGER.exception("RT-BT1 preset movement failed")
            self._set_error(str(err))
            if client is not None and client.is_connected:
                try:
                    await self._write_stop_if_safe(client)
                except Exception:
                    pass
            await self._disconnect_session()

        finally:
            self._set_activity("idle")
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def _write_stop_if_safe(
        self, client: BleakClientWithServiceCache
    ) -> bool:
        """Write vendor 0x2B STOP only when Unlocked is positively known.

        A locked RT-BT1 can be driven into a persistent error/control-inhibited
        condition by 0x2B. Unknown lock state is therefore treated as unsafe for
        STOP, even though ordinary motion controls remain available so successful
        movement can establish the state as Unlocked.
        """
        if self.stop_inhibited:
            _LOGGER.debug(
                "Suppressing 0x2B STOP because Control Lock is not confirmed unlocked"
            )
            return False
        await self._write(client, STOP)
        return True

    async def _send_stop_if_connected(self) -> None:
        client = self._client
        if client is None or not client.is_connected:
            return
        try:
            await self._write_stop_if_safe(client)
        except Exception:
            _LOGGER.debug("Immediate STOP write failed", exc_info=True)

    async def _wait_for_motion_to_end(self, task: asyncio.Task[None]) -> None:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
        except TimeoutError:
            _LOGGER.warning("Motion task did not stop within 3 seconds; cancelling it")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass

    def _motion_done(self, task: asyncio.Task[None]) -> None:
        if self._motion_task is task:
            self._motion_task = None
        if task.cancelled():
            return
        try:
            task.exception()
        except asyncio.CancelledError:
            pass

    async def _replace_motion(self, factory: MotionFactory) -> None:
        """Stop any active HA motion, then start the newly requested one."""
        async with self._replace_lock:
            self._cancel_idle_disconnect()
            old_task = self._motion_task

            if old_task is not None and not old_task.done():
                self._stop_requested.set()
                await self._send_stop_if_connected()
                await self._wait_for_motion_to_end(old_task)

            self._stop_requested.clear()
            task = self.hass.async_create_task(factory())
            self._motion_task = task
            task.add_done_callback(self._motion_done)

    async def async_request_direction(self, upward: bool) -> None:
        """Run the normal Extend/Retract control as a momentary jog."""
        await self.async_request_jog(upward)

    async def async_request_jog(self, upward: bool) -> None:
        self._assert_controls_unlocked()
        await self._replace_motion(lambda: self._run_jog(upward))

    async def async_request_endpoint(self, upward: bool) -> None:
        """Run to the stable fully-extended or fully-retracted endpoint."""
        self._assert_confirmed_unlocked()
        activity = "fully_extending" if upward else "fully_retracting"
        await self._replace_motion(
            lambda: self._run_to_endpoint(upward, activity)
        )

    def _cancel_program_preset_timeout(self) -> None:
        task = self._program_preset_timeout_task
        self._program_preset_timeout_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _program_preset_timeout(self) -> None:
        """Auto-disarm preset programming without clobbering a newer timer."""
        this_task = asyncio.current_task()
        try:
            await asyncio.sleep(10.0)
            if self.program_preset_mode:
                self.program_preset_mode = False
                self._notify_listeners()
        except asyncio.CancelledError:
            pass
        finally:
            # A rapid OFF -> ON can create a newer timeout before this cancelled
            # task reaches finally. Only clear the reference if it still points
            # at this exact task.
            if self._program_preset_timeout_task is this_task:
                self._program_preset_timeout_task = None

    async def async_set_program_preset_mode(self, enabled: bool) -> None:
        """Arm/disarm one-shot preset programming mode."""
        enabled = bool(enabled)
        if enabled:
            self._assert_confirmed_unlocked()
        self._cancel_program_preset_timeout()

        if self.program_preset_mode != enabled:
            self.program_preset_mode = enabled
            self._notify_listeners()

        if enabled:
            self._program_preset_timeout_task = self.hass.async_create_task(
                self._program_preset_timeout()
            )

    async def async_request_preset_action(self, preset: int) -> None:
        """Move to a preset, or save it when Program preset is armed."""
        self._assert_confirmed_unlocked()
        if self.program_preset_mode:
            # One-shot behavior: disarm immediately so a double press cannot
            # overwrite more than one slot accidentally.
            self._cancel_program_preset_timeout()
            self.program_preset_mode = False
            self._notify_listeners()
            await self.async_save_preset(preset)
            return

        await self.async_request_preset(preset)

    async def async_request_preset(self, preset: int) -> None:
        self._assert_confirmed_unlocked()
        await self._replace_motion(lambda: self._run_preset(preset))

    async def _run_absolute_position(self, extension_inches: float) -> None:
        """Move to an absolute extension using the vendor's native 0x1B command."""
        client = None
        requested = float(extension_inches)
        if not math.isfinite(requested):
            raise ValueError("Target position must be finite")
        target_raw = math.floor(requested * 10.0 + 0.5)

        try:
            client = await self._prepare_motion_session()

            # Limits normally arrive in the startup burst. Refresh once before
            # accepting a target outside an unknown/stale range.
            if self.state.lower_limit is None or self.state.upper_limit is None:
                await self._write(client, QUERY_LIMITS)
                await asyncio.sleep(0.060)
                await self._write(client, QUERY_STATUS)
                await asyncio.sleep(0.30)

            lower = self.state.lower_limit
            upper = self.state.upper_limit
            if lower is not None and target_raw < lower:
                raise ValueError(
                    f"Target {requested:.1f} in is below lower limit {lower / 10.0:.1f} in"
                )
            if upper is not None and target_raw > upper:
                raise ValueError(
                    f"Target {requested:.1f} in is above upper limit {upper / 10.0:.1f} in"
                )

            self.state.target_extension_inches = requested
            self._set_activity("moving_to_position")
            self._notify_listeners()

            await self._write(client, build_move_to_position(requested))

            deadline = monotonic() + 40.0
            at_target_since: float | None = None

            while monotonic() < deadline:
                if self._stop_requested.is_set():
                    await self._write_stop_if_safe(client)
                    break

                position = self.state.position
                if (
                    position is not None
                    and abs(position - target_raw) <= ABSOLUTE_POSITION_TOLERANCE_RAW
                ):
                    if at_target_since is None:
                        at_target_since = monotonic()
                    elif (
                        monotonic() - at_target_since
                        >= ABSOLUTE_POSITION_STABLE_SECONDS
                    ):
                        break
                else:
                    at_target_since = None

                await asyncio.sleep(0.1)
            else:
                await self._write_stop_if_safe(client)
                raise RuntimeError(
                    f"Move-to-position timed out before reaching {requested:.1f} in"
                )

            self._set_error(None)

        except Exception as err:
            _LOGGER.exception("RT-BT1 absolute-position movement failed")
            self._set_error(str(err))
            if client is not None and client.is_connected:
                try:
                    await self._write_stop_if_safe(client)
                except Exception:
                    pass
            await self._disconnect_session()

        finally:
            self.state.target_extension_inches = None
            self._set_activity("idle")
            self._notify_listeners()
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def async_request_position(self, extension_inches: float) -> None:
        """Start a native absolute-position move."""
        self._assert_confirmed_unlocked()
        await self._replace_motion(
            lambda: self._run_absolute_position(extension_inches)
        )

    async def async_request_percent(self, position_percent: float) -> None:
        """Move to a percentage of calibrated physical travel.

        Optional user-programmed controller limits constrain the requested target
        but never redefine the 0-100% scale. For example, a request below the
        lower user limit is clamped to that lower limit; reported position then
        snaps the HA slider back to the corresponding physical percentage.
        """
        self._assert_confirmed_unlocked()
        requested = float(position_percent)
        if not math.isfinite(requested):
            raise ValueError("Target percentage must be finite")
        if not 0.0 <= requested <= 100.0:
            raise ValueError("Target percentage must be between 0 and 100")

        physical_min = self.state.physical_min
        physical_max = self.state.physical_max
        if (
            physical_min is None
            or physical_max is None
            or physical_max <= physical_min
        ):
            raise RuntimeError(
                "Physical position range is not calibrated; cannot set percentage"
            )

        target_raw = physical_min + (physical_max - physical_min) * (requested / 100.0)

        # User travel limits are constraints only. They never become new 0/100
        # endpoints for percentage display or conversion.
        if self.state.lower_limit is not None:
            target_raw = max(target_raw, float(self.state.lower_limit))
        if self.state.upper_limit is not None:
            target_raw = min(target_raw, float(self.state.upper_limit))

        await self.async_request_position(target_raw / 10.0)

    async def async_stop(self) -> None:
        """Send vendor STOP while the actuator controls are unlocked.

        STOP is deliberately blocked after Control Lock is active or while the
        lock transaction is in flight. Locking already stops HA-started motion
        before the lock toggle is sent. Keeping 0x2B out of the locked state also avoids
        interleaving STOP with the controller's lock/unlock state machine.
        """
        if self.stop_inhibited:
            _LOGGER.debug(
                "Ignoring STOP while Control Lock is locked, unknown, or transitioning"
            )
            return

        async with self._replace_lock:
            # Re-check after waiting for the motion serializer so a lock transition
            # that began concurrently cannot race a STOP write onto the same session.
            if self.stop_inhibited:
                _LOGGER.debug(
                    "Ignoring STOP because Control Lock is no longer confirmed unlocked"
                )
                return

            task = self._motion_task

            self._set_activity("stopping")
            self._stop_requested.set()
            await self._send_stop_if_connected()

            if task is not None and not task.done():
                await self._wait_for_motion_to_end(task)

            self._stop_requested.clear()
            self._set_activity("idle")
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def _wait_for_lock_state(
        self,
        desired: bool,
        timeout: float,
    ) -> bool:
        """Wait for FE62 to report the requested lock state."""
        deadline = monotonic() + timeout

        while monotonic() < deadline:
            if self.state.locked is desired:
                return True

            self._lock_event.clear()
            remaining = deadline - monotonic()
            if remaining <= 0:
                break

            try:
                await asyncio.wait_for(
                    self._lock_event.wait(),
                    timeout=min(remaining, 0.25),
                )
            except TimeoutError:
                pass

        return self.state.locked is desired

    async def async_set_lock(self, locked: bool) -> None:
        """Request a specific lock state using the vendor's toggle protocol.

        Progressive Motion always writes the same 1F/01 frame for its lock
        control. The resulting 1F response is authoritative:
          payload 01 -> Locked
          payload 00 -> Unlocked

        Therefore Home Assistant must never synthesize separate SET_LOCK and
        SET_UNLOCK frames. Immediately before every possible toggle it performs a
        fresh non-mutating 1F/00 state/synchronization exchange, sends exactly one
        1F/01 toggle only when that fresh state differs from the requested state,
        then waits for the controller to report the result. A missing toggle
        response is never retried automatically.
        """
        locked = bool(locked)

        if self._rehome_active:
            raise RuntimeError("Cannot change Control Lock while RST re-home is in progress")
        if self._calibration_active:
            raise RuntimeError(
                "Cannot change Control Lock while position calibration is in progress"
            )
        if self._travel_limit_active:
            raise RuntimeError(
                "Cannot change Control Lock while travel-limit configuration is in progress"
            )

        if locked:
            # Locking is a safety interlock: stop any HA-started motion first and
            # disarm one-shot preset programming. STOP is sent while the last
            # confirmed state is still unlocked, never after the toggle.
            motion_task = self._motion_task
            if motion_task is not None and not motion_task.done():
                if self.state.locked is not False:
                    raise RuntimeError(
                        "Cannot lock while actuator motion is active and the "
                        "current lock state is not confirmed unlocked"
                    )
                await self.async_stop()

            self._cancel_program_preset_timeout()
            if self.program_preset_mode:
                self.program_preset_mode = False
                self._notify_listeners()

        async with self._lock_operation_lock:
            # A request that became redundant while waiting for the serializer can
            # return without touching BLE.
            current_client = self._client
            if (
                self.state.locked is locked
                and self._lock_transition_target is None
                and current_client is not None
                and current_client.is_connected
            ):
                self._set_error(None)
                return

            self._cancel_idle_disconnect()
            self._lock_transition_target = locked
            self._notify_listeners()
            self._set_activity("locking" if locked else "unlocking")

            client = None
            try:
                client = await self._ensure_session()
                # _ensure_session() temporarily reports "connecting" while opening
                # BLE; restore the explicit lock transition after it returns.
                self._set_activity("locking" if locked else "unlocking")

                # rc32 proved that an additional standalone 1F/00 is not a
                # reliable pre-toggle synchronization: it can be ignored even
                # immediately after session startup has successfully reported the
                # lock state. Re-run the *full captured startup/status burst*
                # instead. The burst is non-mutating and may be retried safely;
                # the 1F/01 toggle itself is still sent at most once.
                fresh_state = await self._synchronize_lock_state_for_toggle(client)

                if not fresh_state or self.state.locked is None:
                    raise RuntimeError(
                        "RT-BT1 lock state is unknown; the controller did not answer "
                        "the fresh read-only control-session sync, so no toggle was sent"
                    )

                # The fresh query is authoritative. If another client or the
                # controller itself already reached the requested state, stop here
                # rather than consuming the synchronization with an unnecessary
                # toggle that would invert the state.
                if self.state.locked is locked:
                    self._set_error(None)
                    self._schedule_idle_disconnect()
                    return

                self._lock_event.clear()
                await self._write(client, LOCK_TOGGLE)
                confirmed = await self._wait_for_lock_state(locked, timeout=1.00)

                if not confirmed:
                    # Never resend the state-changing toggle. A read-only full
                    # synchronization is safe, however, and lets us distinguish a
                    # genuinely ignored toggle from a lost immediate notification.
                    # If the physical state now matches the request, accept it;
                    # otherwise report failure with no automatic toggle retry.
                    readback = await self._synchronize_lock_state_for_toggle(
                        client, attempts=1, timeout=0.90
                    )
                    if readback and self.state.locked is locked:
                        confirmed = True
                    else:
                        self._schedule_idle_disconnect()
                        raise RuntimeError(
                            "RT-BT1 did not reach the requested control-lock state; "
                            "the toggle was not retried automatically"
                        )

                self._set_error(None)
                self._schedule_idle_disconnect()

            except Exception as err:
                _LOGGER.exception("RT-BT1 lock toggle failed")
                self._set_error(str(err))

                # A live session is intentionally retained after a logical toggle
                # timeout, matching Progressive Motion. Only tear down BLE when the
                # transport itself has actually failed/disconnected.
                if client is None or not client.is_connected:
                    try:
                        await self._disconnect_session()
                    except Exception:
                        _LOGGER.debug(
                            "Disconnect after lock transport failure failed",
                            exc_info=True,
                        )
                elif self._idle_task is None:
                    self._schedule_idle_disconnect()
                raise

            finally:
                self._lock_transition_target = None
                self._set_activity("idle")
                self._notify_listeners()

    async def _read_travel_limits_snapshot(
        self,
        client: BleakClientWithServiceCache,
        *,
        timeout: float = 1.0,
    ) -> tuple[int | None, int | None]:
        """Read one authoritative travel-limit snapshot from the controller.

        A cleared controller answers 0x20 without following 0x21/0x22 frames.
        Track fresh response counts so absence in this specific response burst can
        safely clear stale in-memory limit values. This is deliberately read-only.
        """
        flags_before = self._limit_flags_rx_count
        upper_before = self._upper_limit_rx_count
        lower_before = self._lower_limit_rx_count

        await self._write(client, QUERY_STATUS)

        deadline = monotonic() + timeout
        while monotonic() < deadline:
            if self._limit_flags_rx_count > flags_before:
                break
            await asyncio.sleep(0.02)
        else:
            raise RuntimeError("RT-BT1 did not return travel-limit status")

        # The 0x21/0x22 frames, when present, immediately follow 0x20. Allow the
        # remainder of that notification burst to settle before interpreting
        # their absence as 'no programmed limit'.
        await asyncio.sleep(0.25)

        upper = self.state.upper_limit if self._upper_limit_rx_count > upper_before else None
        lower = self.state.lower_limit if self._lower_limit_rx_count > lower_before else None

        changed = False
        if self.state.upper_limit != upper:
            self.state.upper_limit = upper
            changed = True
        if self.state.lower_limit != lower:
            self.state.lower_limit = lower
            changed = True
        self.diag_last_travel_limit_snapshot_at = monotonic()
        self.diag_last_travel_limit_snapshot_at_utc = datetime.now(timezone.utc)
        self.diag_last_travel_limit_snapshot_lower = lower
        self.diag_last_travel_limit_snapshot_upper = upper

        if changed:
            self._notify_listeners()

        return lower, upper

    def _assert_limit_configuration_ready(
        self,
        *,
        require_calibration: bool,
        require_position: bool = True,
    ) -> None:
        """Apply shared interlocks for travel-limit configuration."""
        self._assert_confirmed_unlocked()
        if require_calibration and self.calibration_state != "calibrated":
            raise RuntimeError(
                "Calibrate the physical position range before setting travel limits"
            )
        if require_position and self.state.position is None:
            raise RuntimeError("Current actuator position is unknown")
        if self.motion_active:
            raise RuntimeError("Cannot configure travel limits while motion is active")
        if self._lock_transition_target is not None:
            raise RuntimeError(
                "Cannot configure travel limits during a Control Lock transition"
            )

    async def _run_save_travel_limit(self, *, upper: bool) -> None:
        """Save the current actuator position as one user travel limit exactly once."""
        client: BleakClientWithServiceCache | None = None
        label = "upper" if upper else "lower"
        command = SAVE_UPPER_LIMIT if upper else SAVE_LOWER_LIMIT

        try:
            client = await self._ensure_session()
            if self.state.locked is not False:
                raise RuntimeError("Actuator controls are not confirmed unlocked")

            # Refresh current position before taking the snapshot used for local
            # validity checks. The controller itself stores its instantaneous
            # position when the payload-free 0x21/0x22 write is received.
            self._position_event.clear()
            await self._write(client, QUERY_LIMITS)
            try:
                await asyncio.wait_for(self._position_event.wait(), timeout=1.0)
            except TimeoutError:
                pass
            current = self.state.position
            if current is None:
                raise RuntimeError("No current position feedback from RT-BT1")

            lower, existing_upper = await self._read_travel_limits_snapshot(client)
            if upper:
                if lower is not None and current <= lower:
                    raise RuntimeError(
                        "Upper travel limit must be above the current lower travel limit"
                    )
            else:
                if existing_upper is not None and current >= existing_upper:
                    raise RuntimeError(
                        "Lower travel limit must be below the current upper travel limit"
                    )

            self._set_activity(f"setting_{label}_travel_limit")
            self._notify_listeners()

            # Mutating configuration write: send exactly once. Never blindly
            # retry it. Verification below uses only read-only status traffic.
            await self._write(client, command)
            if upper:
                self.diag_upper_limit_writes += 1
                self.diag_last_upper_limit_result = "gatt_write_completed"
            else:
                self.diag_lower_limit_writes += 1
                self.diag_last_lower_limit_result = "gatt_write_completed"
            await asyncio.sleep(0.12)

            verified_lower, verified_upper = await self._read_travel_limits_snapshot(client)
            verified = verified_upper if upper else verified_lower
            if verified is None:
                # One additional READ is safe when the first response burst is
                # incomplete; the mutating write itself is never repeated.
                verified_lower, verified_upper = await self._read_travel_limits_snapshot(client)
                verified = verified_upper if upper else verified_lower
            if verified is None:
                raise RuntimeError(
                    f"RT-BT1 did not confirm the saved {label} travel limit"
                )

            if upper:
                self.diag_upper_limit_verified += 1
                self.diag_last_upper_limit_result = "verified"
            else:
                self.diag_lower_limit_verified += 1
                self.diag_last_lower_limit_result = "verified"
            self._set_error(None)

        except Exception as err:
            if upper:
                self.diag_last_upper_limit_result = "failed"
            else:
                self.diag_last_lower_limit_result = "failed"
            _LOGGER.exception("RT-BT1 %s travel-limit save failed", label)
            self._set_error(str(err))
        finally:
            self._travel_limit_active = False
            self._set_activity("idle")
            self._notify_listeners()
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def _run_reset_travel_limits(self) -> None:
        """Clear programmed user travel limits with one 0x23 write.

        Hardware testing across rc46-rc48 indicates that 0x23 is accepted most
        reliably after the controller has just answered the read-only 0x20
        status/travel-limit query. rc49 therefore restores that native/proven
        preparation context, but unlike rc47 it may retry only the READ-ONLY
        preflight until a fresh 0x20 response is confirmed. If the controller
        never confirms status, the mutating reset is not sent at all.

        Once prepared, 0x23 is sent exactly once. All subsequent retries are
        read-only verification, first on the same BLE session (matching the rc46
        hardware-success path) and then, if necessary, after a reconnect.
        """
        client: BleakClientWithServiceCache | None = None
        reset_write_completed = False
        try:
            client = await self._ensure_session()
            if self.state.locked is not False:
                raise RuntimeError("Actuator controls are not confirmed unlocked")

            self._set_activity("preparing_travel_limit_reset")
            self._notify_listeners()

            # Safe preflight: obtain a fresh 0x20 response before attempting the
            # mutating 0x23. Read-only failures may be retried/reconnected freely.
            preflight_error: Exception | None = None
            preflight_snapshot: tuple[int | None, int | None] | None = None
            for attempt in range(3):
                try:
                    self.diag_reset_preflight_queries += 1
                    preflight_snapshot = await self._read_travel_limits_snapshot(
                        client, timeout=1.25
                    )
                    self.diag_reset_preflight_confirmed += 1
                    preflight_error = None
                    break
                except Exception as err:
                    preflight_error = err
                    if attempt + 1 >= 3:
                        break
                    await self._disconnect_session()
                    await asyncio.sleep(0.25)
                    client = await self._ensure_session()
                    await asyncio.sleep(0.15)

            if preflight_snapshot is None:
                self.diag_last_reset_result = "preflight_status_unconfirmed_no_write"
                raise RuntimeError(
                    "RT-BT1 did not confirm travel-limit status; reset was not sent"
                ) from preflight_error

            lower, upper = preflight_snapshot
            if lower is None and upper is None:
                self.diag_last_reset_result = "no_limits_reported"
                self._set_error(None)
                return

            self._set_activity("resetting_travel_limits")
            self._notify_listeners()

            # Mutating configuration write: exactly once per user request. A
            # completed response=False GATT write is not itself proof that the
            # controller accepted the command; authoritative proof is readback.
            await self._write(client, RESET_TRAVEL_LIMITS)
            reset_write_completed = True
            self.diag_reset_writes += 1
            self.diag_last_reset_result = "gatt_write_completed"

            # Preserve the successful rc46 cadence: leave the session intact and
            # let the controller commit before the first read-only verification.
            await asyncio.sleep(0.35)
            self._set_activity("verifying_travel_limit_reset")
            self._notify_listeners()

            verification_error: Exception | None = None
            last_snapshot: tuple[int | None, int | None] | None = None

            for attempt in range(3):
                try:
                    # First two verification reads remain on the same session.
                    # Only the final attempt reconnects if status is still missing
                    # or stale. No path below ever resends 0x23.
                    if attempt == 2:
                        await self._disconnect_session()
                        await asyncio.sleep(0.25)
                        client = await self._ensure_session()
                        await asyncio.sleep(0.15)
                    elif attempt == 1:
                        await asyncio.sleep(0.35)

                    self.diag_reset_verification_queries += 1
                    last_snapshot = await self._read_travel_limits_snapshot(
                        client, timeout=1.50
                    )
                    verification_error = None

                    lower, upper = last_snapshot
                    if lower is None and upper is None:
                        self.diag_reset_verified_clears += 1
                        self.diag_last_reset_result = "verified_cleared"
                        self._set_error(None)
                        return

                    # A fresh response still showing limits may simply precede
                    # completion of the controller's nonvolatile commit. Continue
                    # with later READ-ONLY verification; never resend 0x23.
                    self.diag_last_reset_result = "verification_limits_still_present"

                except Exception as err:
                    verification_error = err
                    self.diag_last_reset_result = "verification_status_missing"

            if last_snapshot is not None:
                lower, upper = last_snapshot
                if lower is not None or upper is not None:
                    self.diag_last_reset_result = "controller_limits_still_present"
                    raise RuntimeError(
                        "RT-BT1 still reports programmed travel limits after reset"
                    )

            self.diag_last_reset_result = "gatt_write_completed_verification_failed"
            raise RuntimeError(
                "RT-BT1 reset GATT write completed once, but cleared travel limits "
                "could not be verified by readback"
            ) from verification_error

        except Exception as err:
            if not reset_write_completed and self.diag_last_reset_result in ("requested", None):
                self.diag_last_reset_result = "pre_write_error"
            _LOGGER.exception("RT-BT1 travel-limit reset failed")
            self._set_error(str(err))
        finally:
            self._travel_limit_active = False
            self._set_activity("idle")
            self._notify_listeners()
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def async_set_lower_travel_limit(self) -> None:
        """Save the current position as the controller's lower travel limit."""
        self._assert_limit_configuration_ready(require_calibration=False)
        async with self._replace_lock:
            if self._travel_limit_active:
                raise RuntimeError("Travel-limit configuration is already in progress")
            self.diag_lower_limit_requests += 1
            self.diag_last_lower_limit_result = "requested"
            self._cancel_idle_disconnect()
            self._travel_limit_active = True
            self._notify_listeners()
            task = self.hass.async_create_task(self._run_save_travel_limit(upper=False))
            self._motion_task = task
            task.add_done_callback(self._motion_done)

    async def async_set_upper_travel_limit(self) -> None:
        """Save the current position as the controller's upper travel limit."""
        self._assert_limit_configuration_ready(require_calibration=False)
        async with self._replace_lock:
            if self._travel_limit_active:
                raise RuntimeError("Travel-limit configuration is already in progress")
            self.diag_upper_limit_requests += 1
            self.diag_last_upper_limit_result = "requested"
            self._cancel_idle_disconnect()
            self._travel_limit_active = True
            self._notify_listeners()
            task = self.hass.async_create_task(self._run_save_travel_limit(upper=True))
            self._motion_task = task
            task.add_done_callback(self._motion_done)

    async def async_reset_travel_limits(self) -> None:
        """Clear controller travel limits while preserving physical calibration."""
        self._assert_limit_configuration_ready(
            require_calibration=False, require_position=False
        )
        async with self._replace_lock:
            if self._travel_limit_active:
                raise RuntimeError("Travel-limit configuration is already in progress")
            self.diag_reset_requests += 1
            self.diag_last_reset_result = "requested"
            self._cancel_idle_disconnect()
            self._travel_limit_active = True
            self._notify_listeners()
            task = self.hass.async_create_task(self._run_reset_travel_limits())
            self._motion_task = task
            task.add_done_callback(self._motion_done)

    async def async_load_persistent_state(self) -> None:
        """Load learned physical calibration before entities are created.

        rc42 uses a hardware-address-keyed Home Assistant Store so learned
        endpoints survive config-entry recreation. For upgrades, migrate first
        from rc40/rc41's current entry-keyed store and then from rc38/rc39
        ConfigEntry.options when either contains a valid complete range.
        """

        def _valid_range(data: object) -> tuple[int, int] | None:
            if not isinstance(data, dict):
                return None
            stored_min = data.get(OPT_PHYSICAL_MIN_RAW)
            stored_max = data.get(OPT_PHYSICAL_MAX_RAW)
            if (
                isinstance(stored_min, int)
                and isinstance(stored_max, int)
                and stored_max > stored_min
            ):
                return stored_min, stored_max
            return None

        learned = _valid_range(await self._calibration_store.async_load())

        if learned is None:
            learned = _valid_range(await self._legacy_calibration_store.async_load())
            if learned is not None:
                minimum, maximum = learned
                await self._calibration_store.async_save(
                    {
                        OPT_PHYSICAL_MIN_RAW: minimum,
                        OPT_PHYSICAL_MAX_RAW: maximum,
                    }
                )

        if learned is None:
            learned = _valid_range(dict(self.entry.options))
            if learned is not None:
                minimum, maximum = learned
                await self._calibration_store.async_save(
                    {
                        OPT_PHYSICAL_MIN_RAW: minimum,
                        OPT_PHYSICAL_MAX_RAW: maximum,
                    }
                )

        if learned is not None:
            minimum, maximum = learned
            self.state.physical_min = minimum
            self.state.physical_max = maximum

    async def _persist_physical_calibration(self, minimum: int, maximum: int) -> None:
        """Persist learned physical range in dedicated Home Assistant storage."""
        await self._calibration_store.async_save(
            {
                OPT_PHYSICAL_MIN_RAW: int(minimum),
                OPT_PHYSICAL_MAX_RAW: int(maximum),
            }
        )

    async def _calibration_drive_endpoint(
        self,
        client: BleakClientWithServiceCache,
        *,
        upward: bool,
        activity: str,
    ) -> int | None:
        """Drive to a physical endpoint using six fresh identical position samples.

        Return the settled raw position. Return None when the user intentionally
        interrupts calibration with STOP.
        """
        command = RAISE if upward else LOWER
        self._set_activity(activity)

        recent_positions: deque[int] = deque(maxlen=CALIBRATION_STABLE_SAMPLES)
        last_position_rx_count = self._position_rx_count
        deadline = monotonic() + CALIBRATION_ENDPOINT_TIMEOUT_SECONDS

        while monotonic() < deadline:
            if self._stop_requested.is_set():
                return None

            # Count only fresh 0x01 traffic. This prevents a cached position from
            # becoming a false endpoint when notifications stop arriving.
            if self._position_rx_count != last_position_rx_count:
                last_position_rx_count = self._position_rx_count
                position = self.state.position
                if position is not None:
                    recent_positions.append(position)
                    if (
                        len(recent_positions) == CALIBRATION_STABLE_SAMPLES
                        and len(set(recent_positions)) == 1
                    ):
                        return position

            await self._write(client, command)
            await asyncio.sleep(REPEAT_INTERVAL_SECONDS)

        direction = "upper" if upward else "lower"
        raise RuntimeError(
            f"Position calibration timed out while finding the physical {direction} endpoint"
        )

    async def _calibration_restore_position(
        self,
        client: BleakClientWithServiceCache,
        target_raw: int,
    ) -> bool:
        """Return the actuator to its pre-calibration position without remapping %."""
        minimum = self.state.physical_min
        maximum = self.state.physical_max
        if minimum is None or maximum is None or maximum <= minimum:
            raise RuntimeError("Physical position range is not calibrated")

        target_raw = max(minimum, min(maximum, int(target_raw)))
        target_inches = target_raw / 10.0
        self.state.target_extension_inches = target_inches
        self._set_activity("position_calibration_restoring")
        self._notify_listeners()

        await self._write(client, build_move_to_position(target_inches))

        deadline = monotonic() + CALIBRATION_RESTORE_TIMEOUT_SECONDS
        at_target_since: float | None = None

        while monotonic() < deadline:
            if self._stop_requested.is_set():
                return False

            position = self.state.position
            if position is not None and abs(position - target_raw) <= 1:
                if at_target_since is None:
                    at_target_since = monotonic()
                elif monotonic() - at_target_since >= 0.5:
                    return True
            else:
                at_target_since = None

            await asyncio.sleep(0.1)

        raise RuntimeError(
            "Position calibration learned the endpoints but timed out while "
            "returning to the starting position"
        )

    async def _run_position_calibration(self) -> None:
        """Learn and persist this installation's true physical actuator range.

        Calibration is only valid with user-programmed travel limits cleared. It
        records the natural lower and upper endpoints independently of 0x21/0x22,
        then returns to the position from which calibration started.
        """
        client: BleakClientWithServiceCache | None = None
        original_position: int | None = None

        try:
            client = await self._ensure_session()
            if self.state.locked is not False:
                raise RuntimeError("Actuator controls are not confirmed unlocked")

            # Give configured 0x21/0x22 limits another chance to surface before
            # intentionally traversing the full mechanism. If either exists,
            # calibration would only learn the user limit, not the physical end.
            self._set_activity("position_calibration_checking_limits")
            await self._write(client, QUERY_STATUS)
            await asyncio.sleep(0.45)
            if self.state.lower_limit is not None or self.state.upper_limit is not None:
                raise RuntimeError(
                    "Clear the controller travel limits before calibrating the physical range"
                )

            if self.state.position is None:
                self._position_event.clear()
                await self._write(client, QUERY_LIMITS)
                try:
                    await asyncio.wait_for(self._position_event.wait(), timeout=1.0)
                except TimeoutError:
                    pass
            if self.state.position is None:
                raise RuntimeError(
                    "No position feedback from RT-BT1; cannot calibrate position range"
                )

            original_position = self.state.position

            minimum = await self._calibration_drive_endpoint(
                client,
                upward=False,
                activity="position_calibration_finding_lower",
            )
            if minimum is None:
                self.diag_calibration_stopped += 1
                self.diag_last_calibration_result = "stopped_before_lower_endpoint"
                self._set_error(None)
                return

            await asyncio.sleep(0.35)

            maximum = await self._calibration_drive_endpoint(
                client,
                upward=True,
                activity="position_calibration_finding_upper",
            )
            if maximum is None:
                self.diag_calibration_stopped += 1
                self.diag_last_calibration_result = "stopped_before_upper_endpoint"
                self._set_error(None)
                return

            if maximum <= minimum:
                raise RuntimeError(
                    f"Invalid physical range learned: lower {minimum}, upper {maximum}"
                )

            # Commit only after both physical endpoints have been independently
            # learned *and* durable storage succeeds. This prevents Home Assistant
            # from showing Calibrated for a range that would disappear on restart.
            await self._persist_physical_calibration(minimum, maximum)
            self.state.physical_min = minimum
            self.state.physical_max = maximum
            self._notify_listeners()

            await asyncio.sleep(0.35)

            restore_completed = True
            if original_position is not None:
                restore_completed = await self._calibration_restore_position(client, original_position)

            self.diag_calibration_completed += 1
            self.diag_last_calibration_result = (
                "completed" if restore_completed else "completed_restore_stopped"
            )
            self._set_error(None)

        except asyncio.CancelledError:
            self.diag_last_calibration_result = "cancelled"
            raise
        except Exception as err:
            self.diag_calibration_failures += 1
            self.diag_last_calibration_result = "failed"
            _LOGGER.exception("RT-BT1 physical position calibration failed")
            self._set_error(str(err))
            if client is not None and client.is_connected:
                try:
                    await self._write_stop_if_safe(client)
                except Exception:
                    pass
        finally:
            self.state.target_extension_inches = None
            self._calibration_active = False
            self._set_activity("idle")
            self._notify_listeners()
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def async_request_position_calibration(self) -> None:
        """Start an intentional full-travel physical position calibration."""
        self._assert_confirmed_unlocked()

        if self.state.lower_limit is not None or self.state.upper_limit is not None:
            raise RuntimeError(
                "Clear the controller travel limits before calibrating the physical range"
            )

        if self._lock_transition_target is not None:
            raise RuntimeError(
                "Cannot calibrate while a Control Lock transition is active"
            )

        async with self._replace_lock:
            if self._calibration_active:
                raise RuntimeError("Position calibration is already in progress")
            if self._travel_limit_active:
                raise RuntimeError("Cannot calibrate while travel-limit configuration is in progress")
            if self._rehome_active:
                raise RuntimeError("Cannot calibrate while RST re-home is in progress")

            task = self._motion_task
            if task is not None and not task.done():
                raise RuntimeError(
                    "Cannot calibrate while an actuator motion is active"
                )

            self._cancel_idle_disconnect()
            self._cancel_program_preset_timeout()
            if self.program_preset_mode:
                self.program_preset_mode = False

            self._stop_requested.clear()
            self.diag_calibration_requests += 1
            self.diag_last_calibration_result = "requested"
            self._calibration_active = True
            self._notify_listeners()

            task = self.hass.async_create_task(self._run_position_calibration())
            self._motion_task = task
            task.add_done_callback(self._motion_done)

    async def _run_rst_rehome(self) -> None:
        """Run Progressive Motion's hardware-proven RST/re-home sequence.

        Native behavior on FLTCON-1 is:
          1. Repeat ordinary DOWN at ~200 ms until the reported position is stable.
          2. Pause one second.
          3. Repeat DOWN until F2 F2 04 00 04 7E reports RST state.
          4. Pause one second.
          5. Repeat DOWN until ordinary position responses return.

        No 0x2B STOP or 0x0A release is part of the captured RST sequence.
        """
        client: BleakClientWithServiceCache | None = None
        try:
            client = await self._ensure_session()
            self._set_activity("rst_rehome_descending")

            # Match Progressive Motion's endpoint test: sample the latest reported
            # position on each ~200 ms DOWN tick and stop this phase after six
            # consecutive equal samples. Do not send STOP at the endpoint.
            recent_positions: deque[int] = deque(maxlen=REHOME_STABLE_SAMPLES)
            last_position_rx_count = self._position_rx_count
            deadline = monotonic() + REHOME_DESCEND_TIMEOUT_SECONDS

            while monotonic() < deadline:
                # Only sample after fresh position traffic. This prevents a stale
                # cached value from being mistaken for six stable endpoint samples
                # if FE62 notifications temporarily disappear.
                if self._position_rx_count != last_position_rx_count:
                    last_position_rx_count = self._position_rx_count
                    position = self.state.position
                    if position is not None:
                        recent_positions.append(position)
                        if (
                            len(recent_positions) == REHOME_STABLE_SAMPLES
                            and len(set(recent_positions)) == 1
                        ):
                            break

                await self._write(client, LOWER)
                await asyncio.sleep(REPEAT_INTERVAL_SECONDS)
            else:
                raise RuntimeError(
                    "RST re-home timed out while moving to the lowest position"
                )

            self._set_activity("rst_rehome_cooldown")
            await asyncio.sleep(REHOME_COOLDOWN_SECONDS)

            # The first RST frame is the authoritative transition into the
            # controller's re-home state. A state-changing DOWN is never blindly
            # retried after the event has been observed; we simply cease the
            # periodic writes for the native one-second cooldown.
            self._rst_event.clear()
            self._set_activity("rst_rehome_waiting_for_rst")
            deadline = monotonic() + REHOME_RST_TIMEOUT_SECONDS

            while monotonic() < deadline and not self._rst_event.is_set():
                await self._write(client, LOWER)
                try:
                    await asyncio.wait_for(
                        self._rst_event.wait(),
                        timeout=REPEAT_INTERVAL_SECONDS,
                    )
                except TimeoutError:
                    pass

            if not self._rst_event.is_set():
                raise RuntimeError(
                    "RST re-home timed out waiting for the controller RST response"
                )

            self._set_activity("rst_rehome_cooldown")
            await asyncio.sleep(REHOME_COOLDOWN_SECONDS)

            # Clear only the position event, not the cached position. The first
            # fresh 0x01 position response after RST proves the controller has
            # returned to normal reporting.
            self._position_event.clear()
            self._set_activity("rst_rehome_rehoming")
            deadline = monotonic() + REHOME_NORMAL_TIMEOUT_SECONDS

            while monotonic() < deadline and not self._position_event.is_set():
                await self._write(client, LOWER)
                try:
                    await asyncio.wait_for(
                        self._position_event.wait(),
                        timeout=REPEAT_INTERVAL_SECONDS,
                    )
                except TimeoutError:
                    pass

            if not self._position_event.is_set():
                raise RuntimeError(
                    "RST re-home timed out waiting for normal position feedback"
                )

            # Reconstruct the normal HA state from a fresh read-only startup burst.
            # Lock state is deliberately invalidated here so ordinary controls do
            # not become available until a post-RST 0x1F response confirms it.
            self._set_activity("rst_rehome_refreshing")
            self.state.locked = None
            self._lock_event.clear()
            self._position_event.clear()
            await self._write(client, LOCK_QUERY)
            await asyncio.sleep(0.060)
            await self._write(client, QUERY_LIMITS)
            await asyncio.sleep(0.060)
            await self._write(client, QUERY_STATUS)

            try:
                await asyncio.wait_for(self._position_event.wait(), timeout=1.5)
            except TimeoutError:
                _LOGGER.debug("No position frame received during post-RST refresh")

            await asyncio.sleep(0.20)

            if self.state.locked is None:
                await self._query_lock_state(client, timeout=0.75)

            if self.state.locked is None:
                raise RuntimeError(
                    "RST re-home completed, but post-RST Control Lock state "
                    "could not be confirmed"
                )

            self.diag_rst_completed += 1
            self.diag_last_rst_result = "completed"
            self._set_error(None)

        except asyncio.CancelledError:
            self.diag_last_rst_result = "cancelled"
            raise
        except Exception as err:
            self.diag_rst_failures += 1
            self.diag_last_rst_result = "failed"
            _LOGGER.exception("RT-BT1 RST re-home failed")
            self._set_error(str(err))
            # Never inject STOP into an RST sequence. Ceasing repeated DOWN writes
            # and disconnecting is the safest failure behavior we have verified.
            if client is not None and client.is_connected:
                await self._disconnect_session()
        finally:
            self._rehome_active = False
            self._set_activity("idle")
            self._notify_listeners()
            if self._client is not None and self._client.is_connected:
                self._schedule_idle_disconnect()

    async def async_request_rst_rehome(self) -> None:
        """Start RST re-home without weakening ordinary Control Lock safety.

        RST is intentionally allowed as a recovery/diagnostic operation even when
        the ordinary actuator controls are Locked or Unknown. While it runs, every
        normal movement/configuration action, Control Lock change, and STOP is
        blocked until the RST state machine completes.
        """
        if self._lock_transition_target is not None:
            raise RuntimeError(
                "Cannot start RST re-home while a Control Lock transition is active"
            )

        async with self._replace_lock:
            if self._rehome_active:
                raise RuntimeError("RST re-home is already in progress")

            task = self._motion_task
            if task is not None and not task.done():
                raise RuntimeError(
                    "Cannot start RST re-home while an actuator motion is active"
                )

            self._cancel_idle_disconnect()
            self._cancel_program_preset_timeout()
            if self.program_preset_mode:
                self.program_preset_mode = False

            self._stop_requested.clear()
            self.diag_rst_requests += 1
            self.diag_last_rst_result = "requested"
            self._rehome_active = True
            self._notify_listeners()

            task = self.hass.async_create_task(self._run_rst_rehome())
            self._motion_task = task
            task.add_done_callback(self._motion_done)

    async def _await_stable_position_for_preset_save(
        self,
        client: BleakClientWithServiceCache,
    ) -> int:
        """Return a fresh, stable position before a mutating preset-save write."""
        recent_positions: deque[int] = deque(maxlen=PRESET_SAVE_STABLE_SAMPLES)
        deadline = monotonic() + PRESET_SAVE_SETTLE_TIMEOUT_SECONDS

        while monotonic() < deadline:
            before_rx_count = self._position_rx_count
            self._position_event.clear()
            await self._write(client, QUERY_LIMITS)

            try:
                await asyncio.wait_for(self._position_event.wait(), timeout=1.0)
            except TimeoutError:
                continue

            if self._position_rx_count == before_rx_count:
                continue

            position = self.state.position
            if position is None:
                continue

            recent_positions.append(position)
            if (
                len(recent_positions) == PRESET_SAVE_STABLE_SAMPLES
                and len(set(recent_positions)) == 1
            ):
                return position

            await asyncio.sleep(PRESET_SAVE_SAMPLE_INTERVAL_SECONDS)

        raise RuntimeError(
            "Actuator position did not settle before preset programming"
        )

    async def async_save_preset(self, preset: int) -> None:
        """Save the current actuator position into a controller preset slot."""
        self._assert_confirmed_unlocked()
        if preset not in SAVE_PRESET:
            raise ValueError(f"Invalid preset {preset}")

        async with self._replace_lock:
            motion_task = self._motion_task
            if motion_task is not None and not motion_task.done():
                raise RuntimeError("Cannot save a preset while the actuator is moving")

            if self._lock_transition_target is not None:
                raise RuntimeError(
                    "Cannot save a preset while a control-lock transition is active"
                )

            try:
                self._cancel_idle_disconnect()
                client = await self._ensure_session()

                if self.state.locked is not False:
                    raise RuntimeError("Actuator controls are not confirmed unlocked")

                self._set_activity(f"saving_preset_{preset}")
                self._notify_listeners()

                # Preset programming is ignored by the controller if issued too
                # soon after movement. Verify a fresh stationary position first;
                # this preflight is read-only and the mutating save is still sent
                # exactly once.
                expected_position = await self._await_stable_position_for_preset_save(
                    client
                )

                await self._write(client, SAVE_PRESET[preset])
                await asyncio.sleep(0.15)

                # Refresh the same non-mutating settings/status burst used by the
                # app. 0x25..0x28 are preset-position readbacks in tenths inch.
                await self._write(client, QUERY_LIMITS)
                await asyncio.sleep(0.060)
                await self._write(client, QUERY_STATUS)
                await asyncio.sleep(0.35)
                reported = self.state.presets.get(preset)

                if expected_position is not None and reported != expected_position:
                    await self._write(client, QUERY_LIMITS)
                    await asyncio.sleep(0.060)
                    await self._write(client, QUERY_STATUS)
                    await asyncio.sleep(0.35)
                    reported = self.state.presets.get(preset)

                if expected_position is not None and reported != expected_position:
                    raise RuntimeError(
                        f"Preset {preset} save could not be verified "
                        f"(expected raw {expected_position}, reported {reported})"
                    )

                self._set_error(None)

            except Exception as err:
                _LOGGER.exception("RT-BT1 preset save failed")
                self._set_error(str(err))
            finally:
                self._set_activity("idle")
                if self._client is not None and self._client.is_connected:
                    self._schedule_idle_disconnect()

    async def async_shutdown(self) -> None:
        self._cancel_idle_disconnect()
        self._cancel_program_preset_timeout()

        task = self._motion_task
        if self._rehome_active and task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        else:
            await self.async_stop()

        self._cancel_idle_disconnect()
        await self._disconnect_session()
