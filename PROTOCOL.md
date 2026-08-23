# RT-BT1 BLE Protocol Notes

Reverse-engineered notes for the Progressive Automations RT-BT1 Bluetooth controller used by the Progressive Motion Android app and the Home Assistant `progressive_automations` integration.

Last hardware verification: 2026-08-17. These names are **functional reverse-engineered labels**, not claimed vendor/internal command names unless explicitly stated.

## GATT layouts

| Layout | Service | Write | Notify |
| --- | --- | --- | --- |
| V1 | `FF12` | `FF01` | `FF02` |
| V2 / RT-BT1 tested hardware | `FE60` | `FE61` | `FE62` |

The tested RT-BT1 exposes `FE61` with Write / Write Without Response and `FE62` with Notify. `FE63` and `FE64` also exist on the tested hardware but their protocol role is not established.

## Frame format

Outgoing frames use:

```text
F1 F1 | CMD | LEN | DATA... | CHECKSUM | 7E
```

Incoming frames normally use:

```text
F2 F2 | CMD | LEN | DATA... | CHECKSUM | 7E
```

Checksum:

```text
(CMD + LEN + sum(DATA)) & 0xFF
```

A complete frame is `6 + LEN` bytes. BLE notifications may contain multiple frames concatenated together or may split a frame across notifications, so parsing must operate on a byte stream rather than assuming one notification equals one protocol frame.

## Command map

| Function | Command | Confidence / notes |
| --- | --- | --- |
| Raise / extend | `F1 F1 01 00 01 7E` | Proven on hardware |
| Lower / retract | `F1 F1 02 00 02 7E` | Proven on hardware |
| Save Preset 1 | `F1 F1 03 00 03 7E` | Recovered from native app |
| Save Preset 2 | `F1 F1 04 00 04 7E` | Recovered from native app |
| Recall Preset 1 | `F1 F1 05 00 05 7E` | Proven / native behavior |
| Recall Preset 2 | `F1 F1 06 00 06 7E` | Proven / native behavior |
| Read position + preset state | `F1 F1 07 00 07 7E` | Functional role established from repeated captures |
| Momentary-control release | `F1 F1 0A 00 0A 7E` | Native app sends when a MOM arrow is released |
| Move to absolute position | `F1 F1 1B 02 HI LO CHECKSUM 7E` | Proven on hardware |
| Read/synchronize lock state | `F1 F1 1F 01 00 20 7E` | Proven non-mutating in both Locked and Unlocked states |
| Toggle control lock | `F1 F1 1F 01 01 21 7E` | Proven toggle; **not** SET LOCK |
| Read controller status + travel limits | `F1 F1 20 00 20 7E` | Functional role established from repeated captures |
| Save current position as upper travel limit | `F1 F1 21 00 21 7E` | Proven on FLTCON-1 hardware; configuration-changing |
| Save current position as lower travel limit | `F1 F1 22 00 22 7E` | Proven on FLTCON-1 hardware; configuration-changing |
| Reset / clear travel limits | `F1 F1 23 00 23 7E` | Proven on FLTCON-1 hardware; native app misleadingly labels this "Reset All Settings" |
| Save Preset 3 | `F1 F1 25 00 25 7E` | Recovered from native app |
| Save Preset 4 | `F1 F1 26 00 26 7E` | Recovered from native app |
| Recall Preset 3 | `F1 F1 27 00 27 7E` | Recovered from native app |
| Recall Preset 4 | `F1 F1 28 00 28 7E` | Recovered from native app |
| Explicit STOP | `F1 F1 2B 00 2B 7E` | Native explicit stop / interruption command |

### What `0x07` does

`0x07` is best described as **Read position + preset state**.

On a responsive session it produces the stored preset-position frames and the current actuator-position frame, for example:

```text
F2 F2 25 02 ... 7E   Preset 1 position
F2 F2 26 02 ... 7E   Preset 2 position
F2 F2 27 02 ... 7E   Preset 3 position
F2 F2 28 02 ... 7E   Preset 4 position
F2 F2 01 03 ... 7E   Current position
```

This supersedes the earlier provisional label "query limits". The exact vendor/internal command name remains unknown.

### What `0x20` does

`0x20` is best described as **Read controller status + travel limits**.

When programmed travel-limit readbacks are present, a response burst contains:

```text
F2 F2 20 01 ... 7E   Controller status / flags
F2 F2 21 02 ... 7E   Upper travel limit
F2 F2 22 02 ... 7E   Lower travel limit
```

A hardware test with user limits set to 0.5–15.9 in returned `0x20` payload `0x11`
followed by `0x21=159` and `0x22=5`. After `0x23` cleared those limits, a fresh
disconnect/reconnect and `0x20` query returned only `F2 F2 20 01 00 21 7E`; no
`0x21`/`0x22` frames followed. This proves a meaningful state difference but does
**not** yet establish individual bit meanings inside the status byte.

## Travel-limit programming

Progressive Motion's limit workflow stores the actuator's **current position**; the
`0x21` and `0x22` writes contain no position payload. Live hardware capture proved:

```text
F1 F1 22 00 22 7E   Save current position as lower travel limit
F1 F1 21 00 21 7E   Save current position as upper travel limit
```

The tested lower limit persisted as raw `5` (0.5 in) and the tested upper limit as
raw `159` (15.9 in) across a BLE disconnect/reconnect. Once programmed, the
controller enforces those boundaries against normal manual movement and preset
recall.

### `0x23` native-label correction

Progressive Motion calls `F1 F1 23 00 23 7E` **Reset All Settings**, but that label
does not describe the FLTCON-1 behavior. With programmed travel limits present,
one `0x23` write immediately clears those user limits and restores travel beyond
them. Presets remain unchanged. When no resettable travel limits are present, the
native dialog's Continue control is displayed but disabled/unpressable.

For this integration the functional name is **Reset Travel Limits**. It is not a
firmware flash, factory reset, preset erase, or general settings reset.

## RST re-home sequence

Progressive Automations commonly uses **RST** for controller re-home/diagnostic
initialization. Native Progressive Motion and a live FLTCON-1 HCI capture prove the
BLE workflow uses only the ordinary DOWN command:

```text
1. Repeat F1 F1 02 00 02 7E at ~200 ms until the lowest position is stable.
2. Pause about 1 second.
3. Resume repeated DOWN until the controller reports RST state:
      F2 F2 04 00 04 7E
4. Pause about 1 second.
5. Resume repeated DOWN until normal 0x01 position responses return.
6. Stop repeating DOWN and refresh normal controller state.
```

The native sequence does **not** use `0x2B` STOP or `0x0A` momentary release. A
post-RST snapshot on the tested FLTCON-1 showed presets and configured travel
limits unchanged. Therefore this operation is best described as **RST Re-home
Actuator**, not a factory or hardware-settings reset.

## Home Assistant physical-range calibration

Physical percentage is an integration-level calibration concept, not a new BLE
opcode. RT-BT1 can be attached to actuator systems with different strokes, so the
integration must not treat the tested unit's endpoint values as universal.

With programmed `0x21`/`0x22` travel limits cleared, rc38 learns the natural lower
and upper endpoints by repeating ordinary DOWN/UP commands and requiring six fresh
identical `0x01` position samples at each endpoint. The resulting raw endpoints are
persisted per Home Assistant config entry and become the fixed 0%/100% reference.

Programmed user travel limits remain separate. They may clamp a requested target,
but they never redefine the calibrated physical percentage scale.

## Native-style session synchronization

The Progressive Motion app initializes/refreshes the control session with this cadence:

```text
1F/00   read/synchronize lock state
  60 ms
07      read position + presets
  60 ms
20      read controller status + limits
```

Functionally, this sequence asks the controller for the state needed to reconstruct the control UI: lock state, current position, preset destinations, status, and travel limits.

A cold BLE session may occasionally fail to answer an isolated query. The complete synchronization burst is substantially more reliable than treating the three opcodes as unrelated requests.

## Control-lock protocol

### Read state

```text
TX  F1 F1 1F 01 00 20 7E
```

Confirmed responses:

```text
RX  F2 F2 1F 01 00 20 7E   Unlocked
RX  F2 F2 1F 01 01 21 7E   Locked
```

`1F/00` is non-mutating: it reports/synchronizes lock state and does **not** unlock an already locked controller.

### Change state

```text
TX  F1 F1 1F 01 01 21 7E
```

This command **toggles** the current lock state. Native app decompilation and HCI captures independently confirm that the same command is used for both directions.

Because it is a toggle, it must never be blindly retried after a missing confirmation.

### Required pre-toggle synchronization and settling

Hardware testing showed that the RT-BT1 may ignore a lock toggle unless the control session has just been refreshed. The reliable sequence used by rc34 is:

```text
1. TX 1F/00
2. wait 60 ms
3. TX 07
4. wait 60 ms
5. TX 20
6. wait for fresh 1F lock-state response
7. wait for fresh 01 position response
8. allow ~200 ms for the read/status notification burst to settle
9. if current state already equals requested state: do nothing
10. otherwise TX exactly one 1F/01 toggle
11. confirm resulting state from a new 1F response
```

If the toggle confirmation is missing, a **read-only** synchronization may be performed to learn the resulting physical state, but the toggle itself must not be automatically repeated.

### Persistence observations

Control Lock persists across:

- FE62 notification unsubscribe/re-subscribe.
- Backgrounding the Progressive Motion app while the BLE link remains connected.
- A real Bluetooth link loss/disconnect and later reconnect.

Therefore a new Home Assistant BLE session must not assume Unlocked. It must read the controller's physical lock state before enabling actuator-changing controls.

## Incoming response map

| Opcode | Observed function |
| --- | --- |
| `0x01` | Current actuator position |
| `0x02` | Controller error code |
| `0x04` | FLTCON-1 RST/re-home state (`F2 F2 04 00 04 7E`) |
| `0x1F` | Control-lock state |
| `0x20` | Controller status / flags |
| `0x21` | Upper travel limit |
| `0x22` | Lower travel limit |
| `0x25` | Preset 1 position |
| `0x26` | Preset 2 position |
| `0x27` | Preset 3 position |
| `0x28` | Preset 4 position |

### Position response

Example:

```text
F2 F2 01 03 00 67 0F 7A 7E
```

The position byte is in tenths of an inch (`0x67` = 103 = 10.3 in on the tested unit). The meaning of the following status byte (`0x0F` in many captures) remains unknown; it must **not** be used to infer lock state.

### Absolute-position command

`0x1B` uses integer millimetres, big-endian:

```text
mm = round(inches * 25.4)
F1 F1 1B 02 HI LO CHECKSUM 7E
```

Example for 10.3 in:

```text
F1 F1 1B 02 01 06 24 7E
```

## Errors

Error frames use:

```text
F2 F2 02 01 ERROR_CODE CHECKSUM 7E
```

The integration intentionally exposes the numeric code because vendor labels have not been recovered. Error code `7` was observed during a persistent locked/inhibited condition, but that observation is **not sufficient to claim that Progressive Automations defines Error 7 as "locked"**.

## Safety findings

- Explicit `0x2B` STOP is intentionally blocked while lock state is Locked, transitioning, or Unknown. Hardware testing previously showed that STOP interleaved with lock handling could contribute to a persistent inhibited state.
- RST re-home is a dedicated recovery state machine. While it runs, ordinary motion, preset programming, Control Lock changes, and STOP must not interleave with its repeated-DOWN sequence.
- `0x23` is treated as **Reset Travel Limits** on the tested FLTCON-1. Send the mutating command once, then use read-only state refreshes for verification rather than blindly retrying it.
- `0x21` and `0x22` likewise mutate stored travel limits; save once and verify using read-only status traffic.
- Lock state must come from `0x1F` responses, never from write success or optimistic state changes.

## Known unknowns

The following remain unresolved or only partially decoded:

- Exact vendor/internal names for `0x07` and `0x20`.
- Bit-level meaning of the `0x20` response payload / status flags.
- Meaning of the status byte in the `0x01` position frame.
- Protocol roles, if any, of V2 characteristics `FE63` and `FE64`.
- Official text labels for numeric controller error codes.

These unknowns should remain explicitly marked rather than assigning speculative names in the integration.

## Historical correction

Early release-candidate work incorrectly treated:

```text
F1 F1 1F 01 00 20 7E
```

as a SET UNLOCK command. Differential Locked/Unlocked tests proved this wrong. It is a non-mutating lock-state read/synchronization command. The state-changing command is the single `1F/01` toggle described above.

## Home Assistant travel-limit controls (rc39)

The integration exposes the hardware-proven configuration commands as **Set Lower
Travel Limit**, **Set Upper Travel Limit**, and **Reset Travel Limits**. Lower and
upper limit writes store the actuator's current position. Each mutating command is
sent exactly once; confirmation uses only read-only `0x20` status traffic.

A limit-status snapshot treats fresh `0x21`/`0x22` frames as programmed limits and,
after a fresh `0x20` response settles, treats their absence as no programmed limit.
This allows `0x23` reset verification to clear stale Home Assistant state without
assuming status-bit meanings that have not been decoded.

Physical calibration remains independent and persists when user travel limits are
set or reset. Percentage remains mapped to the calibrated physical endpoints. A
percentage request outside programmed limits is clamped to the corresponding limit;
the UI then reports/snaps to the actual physical percentage at that limit.
