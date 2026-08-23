# Progressive Automations for Home Assistant

Unofficial local Bluetooth integration for Progressive Automations RT-BT1 actuator controllers.

This project is an independent community integration and is not affiliated with or endorsed by Progressive Automations.

## What it provides

The integration exposes an RT-BT1-controlled actuator as native Home Assistant entities and communicates directly over Bluetooth Low Energy.

Primary capabilities include:

- Live physical extension and calibrated 0–100% position.
- Absolute positioning using the controller's native position command.
- Momentary Extend / Retract and explicit Stop.
- Preset 1–4 recall and preset programming.
- Controller lock state and lock/unlock control.
- Per-installation physical endpoint calibration.
- Controller-enforced lower and upper travel limits with verified readback and reset.
- RST re-home recovery action.
- Operation Status feedback during motion, calibration, lock transitions, travel-limit changes, and RST re-home.
- Optional diagnostics for Bluetooth signal, communications, command history, parser recovery, and controller errors.
- Bluetooth auto-discovery with manual-address fallback.

## Tested hardware

Development and hardware validation have centered on the **Progressive Automations RT-BT1** using the V2 GATT layout:

| Layout | Service | Write | Notify | Validation |
| --- | --- | --- | --- | --- |
| V2 | `FE60` | `FE61` | `FE62` | Hardware validated on RT-BT1 |
| V1 | `FF12` | `FF01` | `FF02` | Supported by the integration; less extensively hardware validated |

The integration is actuator-centric and does not assume what is attached to the RT-BT1.

## Requirements

- Home Assistant with a working Bluetooth adapter or Bluetooth proxy path capable of reaching the RT-BT1.
- A Progressive Automations RT-BT1-compatible controller. (https://www.progressiveautomations.ca/products/rt-bt1)
- For local brand images, Home Assistant 2026.3 or newer is recommended.

The stable release was validated on Home Assistant 2026.8.x. Older Home Assistant releases may work, but are not currently part of the tested support matrix.

## Installation

### HACS custom repository

Until this project is accepted into HACS's default repository list, add it as a custom repository:

1. Open HACS in Home Assistant.
2. Add `https://github.com/__GITHUB_OWNER__/progressive-automations-home-assistant` as a **Custom repository** of type **Integration**.
3. Install **Progressive Automations**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add Integration** and search for **Progressive Automations**.

If the controller is advertising and reachable, use **Auto Discovery**. Manual Bluetooth address entry remains available as a fallback.

### Manual installation

Copy:

`custom_components/progressive_automations`

into:

`/config/custom_components/progressive_automations`

Restart Home Assistant, then add the integration from **Settings → Devices & services**.

## Initial setup and calibration

The writable percentage position uses the actuator's **true physical travel range**, not optional user travel limits. A new installation therefore needs a one-time physical range calibration before percentage positioning is available.

1. Ensure controller travel limits are cleared.
2. Enable **Calibrate Position Range** from the device's disabled entities if necessary.
3. Run **Calibrate Position Range**.
4. The integration moves to the lower physical endpoint, then the upper endpoint, learns both positions, and returns approximately to the starting position.

Calibration is stored per device. Optional travel limits can then be set afterward without changing the meaning of 0% and 100%.

### Percentage model

`0%` is the learned physical minimum and `100%` is the learned physical maximum.

Controller travel limits are constraints on that absolute scale. They do **not** remap the scale. For example, if lower and upper travel limits correspond to 20% and 79%, the actuator remains a 0–100% calibrated device, but commands are constrained to the permitted physical region.

## Main entities

Typical entities include:

- **Extension** — measured actuator extension as a Home Assistant distance sensor.
- **Position percentage** — measured position as a percentage of the calibrated physical range.
- **Position percentage** — writable absolute-position control.
- **Operation Status** — current integration operation, normally `Idle`.
- **Position Calibration** — `Required`, `Calibrating`, or `Calibrated`.
- **Preset 1–4** — recall stored presets.
- **Program preset** — arms the next preset press as a save action.
- **Extend / Retract** — momentary jog controls.
- **Stop** — explicit controller stop.
- **Control Lock** — controller lock/unlock state and control.
- **Set Lower Travel Limit / Set Upper Travel Limit / Reset Travel Limits**.
- **Lower Travel Limit / Upper Travel Limit** readback sensors.
- **RST Re-home Actuator** — advanced recovery action.

Some maintenance and diagnostic entities are intentionally disabled by default. Enable them from the Home Assistant device page when needed.

## Optional compact dashboard card

The repository includes an optional compact Lovelace card at:

`dashboard/progressive-automations-card.js`

HACS installs the integration under `custom_components`; it does **not** install this optional frontend file. To use the card:

1. Copy `dashboard/progressive-automations-card.js` to `/config/www/progressive-automations-card.js`.
2. In **Settings → Dashboards → Resources**, add:

   `/local/progressive-automations-card.js?v=1.0.1`

3. Set the resource type to **JavaScript Module**.
4. Add the **Progressive Automations** card to a dashboard.

See [DASHBOARD.md](DASHBOARD.md) for card behavior and troubleshooting.

## Diagnostics and bug reports

Home Assistant's **Download Diagnostics** output contains the most useful state when investigating a problem, including command counts, BLE session information, parser/recovery counters, calibration state, and travel-limit state. Bluetooth MAC addresses are redacted by the integration's diagnostics output.

If a problem occurs, download diagnostics **before restarting or reloading the integration** when possible, then attach the JSON to the GitHub issue.

Routine parser recovery entries can occur because BLE notification boundaries do not necessarily align with RT-BT1 protocol frame boundaries. A recovered frame without checksum failures is not by itself evidence of corrupted controller data.

## Safety

This integration can move physical equipment. Keep the actuator and attached mechanism clear of people, animals, cables, furniture, and other obstructions before commanding motion.

Home Assistant automations, controller travel limits, and software lock state should not be treated as certified safety interlocks. Use appropriate mechanical/electrical safeguards for any installation where unexpected motion could cause injury or damage.

The integration deliberately avoids blindly retrying state-changing BLE commands when their physical outcome is uncertain. Read-only synchronization may be retried; mutating operations are designed around verified state and readback where the controller protocol permits it.

## Protocol documentation

The RT-BT1 protocol was reverse-engineered from hardware behavior, Bluetooth captures, and the Progressive Motion application. See [PROTOCOL.md](PROTOCOL.md) for:

- GATT layouts and frame format.
- Evidence-backed command/response mappings.
- Lock-state synchronization behavior.
- Travel-limit behavior.
- Known unknowns and intentionally unresolved protocol fields.
- Safety-relevant command semantics.

The protocol document distinguishes hardware-proven behavior from inferred or unknown behavior rather than assigning speculative meanings.

## Known limitations

- Hardware validation has focused on the tested RT-BT1 V2 controller. Other controller revisions using the same advertised services may behave differently.
- The optional dashboard card requires a separate `/config/www` installation and resource registration.
- Controller error codes are exposed numerically because official text definitions have not been recovered.
- Some RT-BT1 status-byte/flag meanings and the roles of V2 characteristics `FE63`/`FE64` remain unknown.

## Contributing

Bug reports and hardware observations are welcome. For protocol changes, captures and repeatable hardware evidence are strongly preferred over guessed opcode meanings.

See [CONTRIBUTING.md](CONTRIBUTING.md) before changing command sequencing, lock handling, travel-limit reset behavior, or other state-changing operations.

## License

Released under the MIT License. See [LICENSE](LICENSE).

Progressive Automations and related product names/logos are trademarks of their respective owners and are used only to identify compatible hardware.
