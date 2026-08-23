## Summary

Describe the change and why it is needed.

## Hardware / protocol evidence

If this changes BLE commands, timing, parsing, lock behavior, calibration, RST, preset programming, or travel limits, describe the hardware evidence that supports the change.

## Validation

- [ ] Python files compile successfully.
- [ ] JSON/YAML files parse successfully.
- [ ] HACS validation passes or any failure is explained.
- [ ] Hassfest passes or any failure is explained.
- [ ] State-changing commands are not blindly retried.
- [ ] Hardware behavior was tested when this PR changes controller behavior.
