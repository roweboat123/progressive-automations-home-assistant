# Progressive Automations compact dashboard card

The optional compact card provides a focused actuator UI without exposing the deeper maintenance and diagnostic entities.

## Installation

Copy:

`dashboard/progressive-automations-card.js`

to:

`/config/www/progressive-automations-card.js`

Then add the following Home Assistant dashboard resource as a **JavaScript Module**:

`/local/progressive-automations-card.js?v=1.0.1`

The query string is a cache-buster. Increment it after replacing the JavaScript file if a browser or mobile WebView continues to load an older copy.

## Card behavior

The card shows the measured physical extension and percentage together. It exposes percentage positioning, preset recall/programming, momentary Extend/Retract, Stop, and lock/unlock behavior.

**Operation Status** is shown near the position header while a non-idle operation is active. `Idle` is intentionally hidden in the compact presentation.

The card follows the integration's authoritative lock state:

- **Unlocked:** normal motion, presets, percentage positioning, programming, and Stop are available.
- **Locked:** motion-related controls are disabled; only lock control remains actionable.
- **Unknown / Locking / Unlocking:** actuator-changing controls remain disabled until the controller reports a confirmed state.

The percentage slider represents the calibrated physical 0–100% range. Optional controller travel limits act as hard physical fences and do not redefine the percentage scale.

## Mobile / WebView note

v1.0.1 includes the mobile/WebView compatibility fix validated against the Home Assistant mobile frontend. It also prevents duplicate custom-element registration and removes the former redundant integration/device subtitle.

If the card works on desktop but a mobile client shows a red **Configuration Error** after updating the file, change the resource cache-buster (for example, from `?v=1.0.0` to `?v=1.0.1`) and fully close/reopen the Home Assistant app.

## Diagnostics

Detailed diagnostic entities are intentionally omitted from this compact card. Use the Home Assistant device page and **Download Diagnostics** for troubleshooting.
