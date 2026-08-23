"""Progressive Automations integration for RT-BT1 actuator control."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_ADDRESS, DOMAIN
from .controller import RTBT1Controller

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Retired development diagnostics and superseded controls. Keep the richer
# debug data in Home Assistant's downloadable diagnostics instead of cluttering
# the entity registry.
_DEPRECATED_ENTITY_SUFFIXES = {
    "_bluetooth_connection",
    "_activity",
    "_fe61_writes",
    "_fe62_frames",
    "_fe62_checksum_errors",
    "_fe62_parse_errors",
    "_fe62_recovered_frames",
    "_ble_sessions",
    "_protocol_variant",
    "_last_response_age",
    "_target_extension",
    "_continuous_mode",
    "_use_millimeters",
}


def _async_cleanup_deprecated_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove entities retired by the rc19-rc24 cleanup passes."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform != DOMAIN:
            continue
        if any(entity.unique_id.endswith(suffix) for suffix in _DEPRECATED_ENTITY_SUFFIXES):
            registry.async_remove(entity.entity_id)
            continue

        # Early rc37 builds stored this implementation-detail suffix as the
        # entity's explicit registry name. Clear only that exact legacy value so
        # the current translated name becomes "RST Re-home Actuator" without
        # overwriting a user's intentional custom name.
        if (
            entity.unique_id.endswith("_rst_rehome_actuator")
            and entity.name == "RST Re-home Actuator (Hidden)"
        ):
            registry.async_update_entity(entity.entity_id, name=None)

        # Clear exact legacy implementation-detail names for the two other
        # opt-in maintenance controls. Preserve any user-customized name.
        if (
            entity.unique_id.endswith("_calibrate_position_range")
            and entity.name == "Calibrate Position Range (Hidden)"
        ):
            registry.async_update_entity(entity.entity_id, name=None)
        if (
            entity.unique_id.endswith("_control_lock")
            and entity.name in {"Control Lock (Hidden)", "Control lock (Hidden)"}
        ):
            registry.async_update_entity(entity.entity_id, name=None)

        # rc41-rc44 also set Home Assistant's registry hidden flag on these
        # maintenance entities. Clear only the integration-created hidden flag.
        # They remain disabled by default, but once the user enables one it is
        # visible and the choice persists across reloads.
        if (
            entity.unique_id.endswith(("_calibrate_position_range", "_control_lock"))
            and getattr(entity.hidden_by, "value", entity.hidden_by) == "integration"
        ):
            registry.async_update_entity(entity.entity_id, hidden_by=None)

        # rc37/rc38 created RST with integration-level hidden visibility. rc39
        # keeps it disabled by default but no longer hidden, so enabling the entity
        # does not leave Home Assistant displaying a redundant "(Hidden)" badge.
        # Preserve an explicit user hide; only clear the integration-created one.
        if (
            entity.unique_id.endswith("_rst_rehome_actuator")
            and getattr(entity.hidden_by, "value", entity.hidden_by) == "integration"
        ):
            registry.async_update_entity(entity.entity_id, hidden_by=None)

        # rc21 migrates Control lock from a generic switch to Home Assistant's
        # native lock domain. Remove only the legacy switch entry; the new lock
        # entity intentionally keeps the same unique-id suffix.
        if (
            entity.entity_id.startswith("switch.")
            and entity.unique_id.endswith("_control_lock")
        ):
            registry.async_remove(entity.entity_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate Progressive Automations config entries."""
    if entry.version == 1 and entry.minor_version < 4:
        # RC36 retires rc35's experimental local unit-toggle option. Extension
        # presentation now uses Home Assistant's native distance-unit handling.
        options = dict(entry.options)
        options.pop("use_millimeters", None)
        hass.config_entries.async_update_entry(
            entry,
            options=options,
            minor_version=4,
            version=1,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Progressive Automations RT-BT1 from a config entry."""
    _async_cleanup_deprecated_entities(hass, entry)

    controller = RTBT1Controller(hass, entry, entry.data[CONF_ADDRESS])
    await controller.async_load_persistent_state()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Populate the first state snapshot without blocking integration setup.
    entry.async_create_background_task(
        hass,
        controller.async_refresh(),
        f"{DOMAIN}-refresh-{entry.entry_id}",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        controller = hass.data[DOMAIN].pop(entry.entry_id)
        await controller.async_shutdown()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unloaded
