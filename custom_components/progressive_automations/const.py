"""Constants and protocol helpers for Progressive Automations Bluetooth actuator control."""

import math

DOMAIN = "progressive_automations"
CONF_ADDRESS = "address"

# Per-config-entry physical position calibration. These values describe the
# actuator/controller pair's true mechanical travel in the same raw tenths-inch
# units reported by 0x01 position frames. They are intentionally independent of
# the optional controller travel limits exposed by 0x21/0x22.
OPT_PHYSICAL_MIN_RAW = "physical_min_raw"
OPT_PHYSICAL_MAX_RAW = "physical_max_raw"

# Progressive Motion supports two BLE GATT layouts.
V1_SERVICE_UUID = "0000ff12-0000-1000-8000-00805f9b34fb"
V1_WRITE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
V1_NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

V2_SERVICE_UUID = "0000fe60-0000-1000-8000-00805f9b34fb"
V2_WRITE_UUID = "0000fe61-0000-1000-8000-00805f9b34fb"
V2_NOTIFY_UUID = "0000fe62-0000-1000-8000-00805f9b34fb"

# Read/state requests.
# Functional reverse-engineered labels (exact vendor/internal names are unknown).
# 0x07 refreshes current position plus the four stored preset destinations.
QUERY_LIMITS = bytes.fromhex("F1F10700077E")
# 0x20 refreshes controller status/flags plus upper and lower travel limits.
QUERY_STATUS = bytes.fromhex("F1F12000207E")
# Movement commands.
RAISE = bytes.fromhex("F1F10100017E")
LOWER = bytes.fromhex("F1F10200027E")

# The vendor app uses two different stop-like commands:
# 0x0A is sent when a MOM (momentary) arrow is released.
# 0x2B is the explicit STOP used for interrupting autonomous/endpoint motion.
MOM_RELEASE = bytes.fromhex("F1F10A000A7E")
STOP = bytes.fromhex("F1F12B002B7E")

# Control-lock protocol. Native Progressive Motion captures plus locked/unlocked
# differential tests prove payload 0x00 is a non-mutating READ LOCK STATE request:
#   TX F1 F1 1F 01 00 20 7E
#   RX F2 F2 1F 01 00 20 7E -> Unlocked
#   RX F2 F2 1F 01 01 21 7E -> Locked
# Payload 0x01 is the app's state-changing TOGGLE and must never be retried blindly.
LOCK_QUERY = bytes.fromhex("F1F11F0100207E")
LOCK_TOGGLE = bytes.fromhex("F1F11F0101217E")

MOVE_PRESET = {
    1: bytes.fromhex("F1F10500057E"),
    2: bytes.fromhex("F1F10600067E"),
    3: bytes.fromhex("F1F12700277E"),
    4: bytes.fromhex("F1F12800287E"),
}

# Save the current physical actuator position into a preset slot.
SAVE_PRESET = {
    1: bytes.fromhex("F1F10300037E"),
    2: bytes.fromhex("F1F10400047E"),
    3: bytes.fromhex("F1F12500257E"),
    4: bytes.fromhex("F1F12600267E"),
}

# Travel-limit programming recovered from Progressive Motion and proven on the
# tested FLTCON-1. 0x21/0x22 save the CURRENT actuator position. Despite the
# native app label "Reset All Settings", 0x23 only clears programmed travel limits
# on the tested controller; it does not erase presets or perform a factory reset.
SAVE_UPPER_LIMIT = bytes.fromhex("F1F12100217E")
SAVE_LOWER_LIMIT = bytes.fromhex("F1F12200227E")
RESET_TRAVEL_LIMITS = bytes.fromhex("F1F12300237E")

# Incoming response opcodes.
POSITION_RESPONSE = 0x01
ERROR_RESPONSE = 0x02
# Exact FLTCON-1 RST/re-home response captured from Progressive Motion.
# Frame: F2 F2 04 00 04 7E
RST_RESPONSE = 0x04
LOCK_RESPONSE = 0x1F
LIMIT_FLAGS_RESPONSE = 0x20
MAX_LIMIT_RESPONSE = 0x21
MIN_LIMIT_RESPONSE = 0x22

# Preset-position readback returned in the settings/status burst. Hardware
# captures confirm 0x26 matches Preset 2's live destination (raw tenths inch),
# with the four response opcodes mapping to Presets 1-4.
PRESET_RESPONSE = {
    0x25: 1,
    0x26: 2,
    0x27: 3,
    0x28: 4,
}


def build_move_to_position(extension_inches: float) -> bytes:
    """Build the vendor 0x1B absolute-position command.

    Progressive Motion converts inches to integer millimetres, sends the value
    big-endian, then uses an additive checksum over CMD + LEN + DATA.
    """
    scaled = float(extension_inches) * 25.4
    if not math.isfinite(scaled):
        raise ValueError("Target position must be finite")

    # Dart double.round(), used by Progressive Motion, rounds an exact .5 away
    # from zero. Extension values are non-negative, so floor(x + 0.5) matches it.
    millimetres = math.floor(scaled + 0.5)
    if not 0 <= millimetres <= 0xFFFF:
        raise ValueError("Target position is outside the protocol's 16-bit range")

    high = (millimetres >> 8) & 0xFF
    low = millimetres & 0xFF
    checksum = (0x1B + 0x02 + high + low) & 0xFF
    return bytes((0xF1, 0xF1, 0x1B, 0x02, high, low, checksum, 0x7E))
