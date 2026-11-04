"""Octopus Spain integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady

from homeassistant.core import HomeAssistant

from .credentials import CredentialError, decrypt_credentials, migrate_credentials

from .const import DOMAIN as DOMAIN  # pylint: disable=useless-import-alias

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Octopus Spain from a config entry."""
    try:
        await hass.async_add_executor_job(decrypt_credentials, {**entry.data, **entry.options})
    except CredentialError as err:
        raise ConfigEntryNotReady(str(err)) from None
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version > 2:
        return False
    try:
        data, options = await hass.async_add_executor_job(migrate_credentials, dict(entry.data), dict(entry.options))
    except CredentialError:
        return False
    hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
    return True


async def _async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    # Options contain only ciphertext; avoid recursive listener updates.
    await hass.config_entries.async_reload(config_entry.entry_id)
