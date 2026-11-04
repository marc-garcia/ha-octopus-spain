"""Configure Octopus without persisting or prefilling plaintext credentials."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .credentials import CredentialError, encrypt_credentials
from .lib.octopus_spain import OctopusSpain

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
        vol.Required(CONF_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)


async def validate_and_encrypt(hass, user_input):
    # Fail before sending anything to Octopus if secure storage is unavailable.
    encrypted = await hass.async_add_executor_job(encrypt_credentials, user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
    api = OctopusSpain(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
    if not await api.login():
        return None
    return encrypted


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionFlowHandler()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                encrypted = await validate_and_encrypt(self.hass, user_input)
                if encrypted is not None:
                    return self.async_create_entry(data=encrypted, title="Octopus Spain")
                errors["base"] = "invalid_auth"
            except CredentialError:
                errors["base"] = "secure_storage"
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)


class OptionFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                encrypted = await validate_and_encrypt(self.hass, user_input)
                if encrypted is not None:
                    return self.async_create_entry(data=encrypted, title="Octopus Spain")
                errors["base"] = "invalid_auth"
            except CredentialError:
                errors["base"] = "secure_storage"
            except Exception:
                errors["base"] = "cannot_connect"
        # Deliberately no decrypted defaults, including for the masked password field.
        return self.async_show_form(step_id="init", data_schema=SCHEMA, errors=errors)
