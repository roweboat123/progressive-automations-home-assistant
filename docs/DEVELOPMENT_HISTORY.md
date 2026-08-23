# Progressive Automations migration notes

## rc54

- Presentation-only cleanup for optional diagnostics: Last command and Last command result now use human-readable labels in Home Assistant while raw labels remain in downloaded diagnostics.
- No controller/BLE behavior changes.

## rc53

- Diagnostics-only cleanup; no actuator/controller command behavior changed.
- Diagnostic counters are explicitly scoped to the current integration load.
- Added optional Last successful communication, Last command, Last command result, and Last error entities.
- Added travel-limit snapshot freshness and parser recovery/error details to downloaded diagnostics.
- Removed duplicate flat protocol/reset counters from downloaded diagnostics.
- Redacted Bluetooth MAC addresses from reachability text.

## rc52

- Moves **Operation Status** out of Home Assistant's Diagnostic entity category so it appears with the live actuator sensors on the device page.
- Adds active Operation Status to the bundled compact card directly below the position/percentage header.
- Renames calibration phase text to **Calibrating lower endpoint**, **Calibrating upper endpoint**, and **Returning to pre-calibration position**.
- No BLE protocol, RST, calibration algorithm, travel-limit, or lock behavior is changed from rc51.

## rc51

- Moves **RST Re-home Actuator**, **Calibrate Position Range**, and **Control Lock** to Home Assistant's **Configuration** entity category.
- Keeps their existing disabled-by-default behavior and entity IDs.
- No BLE protocol, calibration, travel-limit, RST, or lock command behavior is changed from rc50.

## rc50

- Keeps the hardware-validated rc49 controller behavior unchanged.
- Adds a live **Operation Status** diagnostic sensor for long-running maintenance actions.
- Expands downloaded diagnostics with authoritative BLE command/frame history and request/result counters for RST re-home, physical calibration, and travel-limit operations.
- Existing calibration storage, entity IDs, and controller settings are unchanged.

## rc49

Reset Travel Limits now requires a confirmed fresh read-only `0x20` status burst before the single `0x23` mutation. Read-only preflight may retry/reconnect; `0x23` never does. Post-reset verification first stays on the same session, then may reconnect for readback. Diagnostics now make clear that a completed GATT write is not itself controller acknowledgement.

## rc48
Travel-limit Reset no longer performs a mandatory fresh `0x20` preflight before the single `0x23` write. Verification now uses receive counters captured before a fresh BLE reconnect so the startup status burst can authoritatively clear stale cached limits. Reset request/write/verification counters were added to diagnostics.

## Upgrading v1.0.0-rc46 to v1.0.0-rc47

This is an in-place upgrade. Do **not** remove or re-add the integration.

1. Replace `/config/custom_components/progressive_automations` with the rc47 integration files.
2. If you use the bundled compact dashboard card, replace its JavaScript file and update the cache-buster to `?v=1.0.0-rc47`.
3. Restart Home Assistant.

RC47 fixes reset verification after hardware testing proved rc46 could successfully clear both physical controller travel limits while the immediate `0x20` readback timed out. The reset mutation remains exactly-once: rc47 never retries `0x23`. It waits for the controller to settle, then performs only read-only `0x07 -> 0x20` synchronization/reconnect attempts so stale limit state is cleared when the controller reports no `0x21/0x22` limits. Physical position calibration is preserved.

## rc40
> **rc43:** Corrects Lower/Upper Travel Limit readback sensors to use the Home Assistant diagnostic entity category. They are read-only configuration readbacks; `EntityCategory.CONFIG` is invalid for sensor entities in Home Assistant 2026.8 and prevented them from loading.

rc40 moves learned physical-range calibration out of `ConfigEntry.options` and into
Home Assistant's dedicated persistent storage helper, keyed per config entry. This
fixes a real rc38/rc39 hardware-test finding where calibration remained valid in the
live controller but returned to **Required** after an integration upgrade/restart.

- Calibration is loaded from persistent storage before entities are created.
- Any valid rc38/rc39 calibration still present in config-entry options is migrated
  one-way into the new store.
- A newly learned range is not exposed as **Calibrated** until the storage write
  succeeds.
- Travel-limit controls and absolute physical 0–100% behavior from rc39 are unchanged.

### Upgrade rc39 → rc40

1. Replace the integration files and restart Home Assistant.
2. If rc39 already lost the prior calibration, **Position Calibration** will still
   show **Required**; run **Calibrate Position Range** once.
3. Restart Home Assistant again and confirm it remains **Calibrated** before testing
   travel-limit controls.

## rc39

rc39 adds controller-backed travel-limit controls while preserving rc38's
installation-specific physical calibration.

- **Set Lower Travel Limit** sends the proven `0x22` save-current-position command once.
- **Set Upper Travel Limit** sends the proven `0x21` save-current-position command once.
- **Reset Travel Limits** sends the proven `0x23` clear command once.
- All three verify state using read-only `0x20` status traffic; mutating commands are never blindly retried.
- Percentage remains tied to physical calibration. Programmed limits only clamp motion.
- Resetting travel limits does **not** erase the persisted physical calibration.
- RST Re-home Actuator remains disabled by default, but is no longer integration-hidden; rc39 also clears the legacy integration-created hidden flag while respecting an explicit user hide.

### Upgrade rc38 → rc39

1. Replace `/config/custom_components/progressive_automations` with the rc39 files.
2. Restart Home Assistant.
3. Confirm **Position Calibration** remains **Calibrated**.
4. Test lower, upper, and reset travel limits one operation at a time.

# Migration notes

## rc38

rc38 separates the actuator's **physical calibrated range** from optional user
travel limits. This fixes percentage control becoming unavailable after travel
limits are cleared.

- Adds **Position Calibration** with Required / Calibrating / Calibrated states.
- Adds **Calibrate Position Range**. It intentionally traverses the natural lower
  and upper endpoints, using six fresh identical position samples at each end.
- The learned physical minimum/maximum are persisted per Home Assistant config
  entry and survive restart.
- Percentage always means physical travel: 0% is the calibrated natural lower
  endpoint and 100% is the calibrated natural upper endpoint.
- Optional `0x21`/`0x22` travel limits constrain commands but do not remap the
  percentage scale.
- RST re-home behavior from rc37 is unchanged.

### Upgrade rc37 → rc38

1. Replace `/config/custom_components/progressive_automations` with the rc38 files.
2. Restart Home Assistant. Do not remove/re-add the integration.
3. With controller travel limits cleared, press **Calibrate Position Range** once.
4. Allow the full lower → upper → return sequence to finish. The Position
   Calibration entity should become **Calibrated** and percentage control should
   become available.

## rc36

rc36 discards the experimental rc35 unit-toggle approach. The Extension entity now
uses Home Assistant's native `distance` sensor semantics: its native and suggested
unit remains inches, while Home Assistant's entity settings can select millimeters
or another supported distance display unit. This is presentation-only and changes
no BLE commands, lock handling, movement behavior, percentage calculations, limits,
or presets.

### Upgrade rc34/rc35 → rc36

1. Replace `/config/custom_components/progressive_automations` with the rc36 files.
2. Restart Home Assistant. Do not remove/re-add the integration.
3. Open the **Extension** entity settings to select the desired display unit.
4. If using the bundled compact card, replace its JavaScript file and update the
   resource cache-buster to `?v=1.0.0-rc36`.

## rc34

rc34 keeps rc33's fresh read-only `1F/00 → 07 → 20` synchronization, but does
not treat the first `0x1F` notification as proof that the synchronization burst
has finished. It now waits for both the fresh lock-state response and the fresh
position response, then waits another 200 ms before the single `1F/01` toggle.
This mirrors the proven session-start timing and avoids placing the toggle into
the tail of the controller's read/status notification burst. The toggle is still
never retried automatically.

### Upgrade rc33 → rc34

1. Replace `/config/custom_components/progressive_automations` with the rc34 files.
2. Restart Home Assistant.
3. If you use the bundled compact dashboard card, replace its JavaScript file and
   update the resource cache-buster to `?v=1.0.0-rc34`.

## rc33

RC33 corrects rc32's pre-toggle synchronization. Hardware testing showed that an
extra standalone `F1 F1 1F 01 00 20 7E` can be ignored even after the controller
has just reported a valid lock state. Before each possible toggle rc33 now uses
the complete captured non-mutating control-session burst:

`1F/00` → 60 ms → `0x07` → 60 ms → `0x20`

Behavior changes from rc32:

- Pre-toggle synchronization uses the full read/status burst, not standalone
  `1F/00`.
- The read-only synchronization burst may be retried automatically; it cannot
  change lock state.
- The `1F/01` state-changing toggle is still sent at most once per user action.
- If the direct toggle response is missed, rc33 performs a read-only burst to
  verify the physical state instead of retrying the toggle.
- Movement and STOP remain unavailable unless Unlocked is positively confirmed.

### Upgrade rc32 → rc33

1. Replace `/config/custom_components/progressive_automations` with the rc33 files.
2. Restart Home Assistant.
3. If using the bundled dashboard resource, update its cache-buster to
   `?v=1.0.0-rc33`.

## rc32

RC32 adds the lock-toggle synchronization discovered during repeated hardware
testing after rc31. A fresh `F1 F1 1F 01 00 20 7E` exchange is required before
each individual `F1 F1 1F 01 01 21 7E` toggle; otherwise the controller can
silently ignore the toggle. This requirement was reproduced for both Lock and
Unlock.

Behavior changes from rc31:

- Every requested Lock/Unlock first performs a new read-only `1F/00` state/sync.
- The fresh response is authoritative; if the requested state already matches, no
  toggle is sent.
- If the state differs, exactly one `1F/01` toggle is sent.
- A missing toggle confirmation is still never retried automatically.
- Movement and STOP remain unavailable unless Unlocked is positively confirmed.

### Upgrade rc31 → rc32

1. Replace `/config/custom_components/progressive_automations` with the rc32 files.
2. Restart Home Assistant.
3. If using the bundled dashboard resource, update its cache-buster to
   `?v=1.0.0-rc32`.

## rc31

RC31 completes the lock-protocol work started in rc30. Differential tests against
a controller known to be Locked and then known to be Unlocked prove that
`F1 F1 1F 01 00 20 7E` is a **read-only lock-state query**:

- `F2 F2 1F 01 00 20 7E` = **Unlocked**.
- `F2 F2 1F 01 01 21 7E` = **Locked**.
- `F1 F1 1F 01 01 21 7E` remains the only state-changing **toggle**.

Behavior changes from rc30:

- Fresh BLE sessions begin Unknown and query the physical lock before any actuator
  command is permitted.
- The captured startup sequence remains `1F/00` → 60 ms → `0x07` → 60 ms → `0x20`.
  If a cold session does not answer the first query, HA retries `1F/00` once after
  the status burst.
- The rc30 movement-as-proof fallback is removed. Extend/Retract are no longer
  available while lock state is Unknown.
- Every movement/preset/percentage/STOP/program-preset action now requires a
  positively confirmed Unlocked state.
- Lock/Unlock never toggles from Unknown; it first retries the read-only query, then
  sends one toggle only if the requested state differs. Toggle timeouts are still
  never automatically retried.
- Idle disconnect keeps the last confirmed state visible, but the next connection
  invalidates that cached state and re-queries before any actuator-changing write.

### Upgrade rc30 → rc31

1. Replace `/config/custom_components/progressive_automations` with the rc31 files.
2. If using the bundled compact card, replace its JavaScript file and update the
   resource cache-buster to `?v=1.0.0-rc31`.
3. Restart Home Assistant. Do not remove/re-add the config entry.
4. No manual jog is required after restart; the integration now reads the lock state
   directly from the controller.

## rc30

RC30 supersedes the lock-protocol assumptions used by rc25-rc29. Native HCI
traffic and the decompiled Progressive Motion lock callback show that `1F/01` is
a **toggle**, while `1F/00` is part of app initialization and is not a working
UNLOCK setter.

- Fresh sessions now reproduce the captured app startup exactly:
  `1F/00` → 60 ms → `0x07` → 60 ms → `0x20`.
- Lock and Unlock no longer use separate command frames. HA sends one `1F/01`
  toggle only when the last known state differs from the requested state.
- HA changes lock state only from the controller's `0x1F` response.
- Toggle timeouts are never auto-retried. The session remains open and the prior
  confirmed state remains visible so the user can retry explicitly.
- On a fresh HA process, lock state begins Unknown. Only momentary Extend/Retract
  are allowed until an HA-commanded position change safely establishes Unlocked;
  a lock response establishes either state directly.
- Percentage, presets, endpoint motion, preset programming, Lock/Unlock, and STOP
  stay unavailable while lock state is Unknown, preventing autonomous movement or
  `0x2B` from being sent to a possibly locked controller.
- rc29 should be treated as retired and should not be reinstalled.

### Upgrade rc29 → rc30

1. Replace `/config/custom_components/progressive_automations` with the rc30 files.
2. If using the bundled compact card, replace its JavaScript file and update the
   resource cache-buster to `?v=1.0.0-rc30`.
3. Restart Home Assistant. Do not remove/re-add the config entry.
4. After restart, tap **Extend** or **Retract** once. A real position change proves
   Unlocked and enables percentage, presets, STOP, and state-directed Lock/Unlock.

> Historical rc25-rc29 notes used the then-current but incorrect SET LOCK / SET
> UNLOCK interpretation. RC30 is the protocol authority for `0x1F` behavior.

## rc27

- STOP is now lock-sensitive. It is unavailable while Control Lock is **Locked**, **Locking**, or **Unlocking**.
- The controller backend also ignores direct STOP calls while locked/transitioning, so a service call cannot interleave `0x2B` with the lock/unlock BLE transaction.
- Locking still stops any HA-started movement first, before the lock transition is published, so the safety shutdown behavior is preserved.
- The compact card disables STOP together with the percentage, preset, and movement controls while locked.

## Upgrading v1.0.0-rc26 to v1.0.0-rc27

1. Replace `/config/custom_components/progressive_automations` with the rc27 integration files.
2. If you use the bundled compact dashboard card, replace its JavaScript file and update the cache-buster to `?v=1.0.0-rc27`.
3. Restart Home Assistant. No delete/re-add is required.

## rc26

- Replaces the detached lock worker with one serialized lock/unlock transaction. This removes the stale transition state that could leave movement entities grayed out after the controller had already finished locking or unlocking.
- Every lock transition now publishes an explicit start and completion update to Home Assistant, including failure cleanup.
- Historical rc26 behavior: when a controller appeared `Unlocked`, rc26 re-sent `1F/00` and refreshed status. RC30 later proved the old "UNLOCK" label for `1F/00` was incorrect.
- The compact percentage slider is state-driven. After a user releases it, the thumb returns to the last measured percentage and then follows live position telemetry, so a failed/rejected command cannot leave the slider bar disagreeing with the displayed percentage.
- The LOCK/UNLOCK action is disabled while a lock transition is in progress, avoiding overlapping UI requests.

## Upgrading v1.0.0-rc25 to v1.0.0-rc26

1. Replace `/config/custom_components/progressive_automations` with the rc26 integration files.
2. If you use the bundled compact dashboard card, replace its JavaScript file and update the cache-buster to `?v=1.0.0-rc26`.
3. Restart Home Assistant. No delete/re-add is required.

## rc25

- Fixes a lock/unlock readiness race where movement controls could become available before the BLE lock transaction had actually finished.
- Historical rc25 behavior: it treated `1F/00` as UNLOCK before sending `0x07` → `0x20`. RC30 later proved that `1F/00` interpretation incorrect.
- After unlock, the refreshed BLE session stays warm so the first movement/percentage command can run immediately.
- Movement controls remain unavailable for the entire lock/unlock transaction and re-enable only when the controller is ready.

## Upgrading v1.0.0-rc23 to v1.0.0-rc25

1. Replace `/config/custom_components/progressive_automations` with the rc25
   integration files.
2. If you use the bundled compact dashboard card, replace its JavaScript file and
   update the cache-buster to `?v=1.0.0-rc25`.
3. Restart Home Assistant. No delete/re-add is required.

RC24 retires the **Continuous motion** switch completely. Normal Extend / Retract
are always momentary jog controls; Fully extend / Fully retract retain the sustained
endpoint behavior, so the global mode toggle no longer adds a distinct capability.
The old `*_continuous_mode` entity is removed automatically from the entity registry.

## Upgrading v1.0.0-rc22 to v1.0.0-rc23

1. Replace `/config/custom_components/progressive_automations` with the rc23
   integration files.
2. If you use the bundled compact dashboard card, replace its JavaScript file and
   update the cache-buster to `?v=1.0.0-rc23`.
3. Restart Home Assistant. No delete/re-add is required.

RC23 makes Control Lock a real-time interlock for every actuator-changing entity.
Locked/locking/unlocking makes percentage, jog, preset, preset-programming, endpoint,
and advanced motion controls unavailable; only Control Lock remains available.
The controller backend also rejects movement requests while locked, so service calls
cannot bypass the UI. Locking during an HA-started move stops it first.


## Upgrading v1.0.0-rc21 to v1.0.0-rc22

1. Replace `/config/custom_components/progressive_automations` with the rc22
   `progressive_automations` folder.
2. If you use the compact card, replace the JavaScript file and change the resource
   cache-buster to `?v=1.0.0-rc22`.
3. Restart Home Assistant.

RC22 removes **Continuous motion** from the default control surface. The capability
is not deleted: its entity remains available as an advanced entity, disabled by
default, and users can re-enable it from the device entity list. Existing rc21
entries are migrated once so the previously enabled Continuous motion switch becomes
disabled; if a user later re-enables it, rc22 does not disable it again.

The compact card no longer resolves or displays Continuous motion. Extend/Retract
remain momentary jog controls, the percentage slider remains the primary positioning
control, and Fully extend / Fully retract retain sustained movement as advanced
buttons.

## Upgrading v1.0.0-rc20 to v1.0.0-rc21

1. Replace `/config/custom_components/progressive_automations` with the rc21
   `progressive_automations` folder.
2. If you use the compact card, replace the JavaScript file and change the resource
   cache-buster to `?v=1.0.0-rc21`.
3. Restart Home Assistant.

RC21 migrates **Control lock** from a generic switch entity to a native Home
Assistant lock entity. The legacy `switch.*control_lock` registry entry is removed
automatically and a new `lock.*control_lock` entity is created. If an automation
explicitly referenced the old switch entity ID, update it to the new lock entity.

The lock transaction logic also now preserves a rapid opposite request instead of
discarding it, so an immediate Lock → Unlock recovery remains reliable.

# Progressive Automations migration notes

## Upgrading v1.0.0-rc19 to v1.0.0-rc20

This is an in-place upgrade. Do **not** remove or re-add the integration.

1. Replace `/config/custom_components/progressive_automations` with the rc20
   `progressive_automations` folder.
2. Restart Home Assistant.
3. If you use the bundled compact card, replace
   `/config/www/progressive-automations-card.js` and update its dashboard resource
   cache-buster to `?v=1.0.0-rc20`.
4. Hard-refresh the browser/app if the old card remains cached.

RC20 automatically removes the retired inch-based Position number entity
(`*_target_extension`) from the entity registry. The percentage position control
remains and uses the same native absolute-position BLE command.

The Communication diagnostic keeps its existing unique ID for compatibility; only
its displayed name changes from **Communication problem** to
**Communication status**.
