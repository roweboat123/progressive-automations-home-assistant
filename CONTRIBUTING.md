# Contributing

Contributions, hardware observations, logs, and reproducible bug reports are welcome.

## Before changing BLE behavior

The RT-BT1 protocol contains state-changing operations whose result can be unsafe to retry blindly. Please preserve these principles unless new hardware evidence proves a different behavior is required:

1. **Do not blindly retry mutating commands.** If a write succeeds at the GATT layer but the controller's physical result is uncertain, use read-only synchronization/readback before deciding what happened.
2. **Treat lock state as controller-reported state.** Do not infer lock/unlock from write success or from whether motion happens.
3. **Serialize motion and configuration operations.** Avoid overlapping movement, lock transitions, calibration, RST, travel-limit changes, and preset programming.
4. **Keep calibration separate from user travel limits.** Physical 0–100% calibration describes the actuator's natural range; optional travel limits constrain that scale rather than redefining it.
5. **Do not assign speculative names to unknown protocol fields.** Update `PROTOCOL.md` with the evidence and confidence level.

## Useful bug-report evidence

When possible, include:

- Home Assistant version.
- Integration version.
- RT-BT1/controller revision if known.
- Whether the device uses the V2 `FE60/FE61/FE62` or V1 `FF12/FF01/FF02` layout.
- Exact steps to reproduce.
- Home Assistant Download Diagnostics captured before restart/reload.
- Relevant logs.
- Whether the physical actuator actually moved or changed state.

## Pull requests

Keep behavior changes small and evidence-based. A pull request that changes an opcode, timing sequence, retry rule, parser rule, lock transition, calibration flow, or travel-limit flow should explain why the existing hardware-validated behavior is insufficient and what evidence supports the replacement.

Run the repository validation workflows before requesting review. Python files should at minimum compile successfully, and JSON/YAML files should remain parseable.
