# Changelog

All notable public changes to this project are documented here.

## 1.0.1 - 2026-08-23

### Fixed

- Improved optional compact dashboard card compatibility with embedded/mobile Home Assistant WebViews.
- Prevented duplicate custom-element/custom-card registration.
- Removed the redundant dashboard-card subtitle.

### Unchanged

- No BLE protocol, controller, entity, calibration, preset, lock, travel-limit, RST, or motion behavior changed from v1.0.0.

## 1.0.0 - 2026-08-23

- First stable public release based on the hardware-validated rc56 controller codebase.
- Calibrated absolute 0–100% positioning across the learned physical actuator range.
- Preset 1–4 recall and programming with settling/readback safeguards.
- Controller lock synchronization and control.
- Physical range calibration and RST re-home recovery.
- Controller travel-limit set/reset/readback while preserving the absolute percentage scale.
- Operation Status feedback and expanded redacted diagnostics.
- Automatic support for the known V2 and V1 RT-BT1 GATT layouts.
