"""Configure Octopus without persisting or prefilling plaintext credentials."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType, NumberSelector, NumberSelectorConfig, ObjectSelector, DateSelector

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .credentials import CredentialError, encrypt_credentials, decrypt_credentials, ENCRYPTED, FORMAT
from .cost_calculation import CONF_ENERGY_PRICE, validate_price, CONF_COST_PERIODS, validate_cost_periods, CostPeriodError
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
                if user_input.get(CONF_EMAIL) or user_input.get(CONF_PASSWORD):
                    if not user_input.get(CONF_EMAIL) or not user_input.get(CONF_PASSWORD):
                        return self.async_show_form(step_id="init", data_schema=self._schema(), errors={"base": "credentials_required"})
                    encrypted = await validate_and_encrypt(self.hass, user_input)
                else:
                    current = {**self.config_entry.data, **self.config_entry.options}
                    await self.hass.async_add_executor_job(decrypt_credentials, current)
                    encrypted = {FORMAT: current[FORMAT], ENCRYPTED: current[ENCRYPTED]}
                if encrypted is not None:
                    if user_input.get(CONF_ENERGY_PRICE) is not None:
                        encrypted[CONF_ENERGY_PRICE] = float(validate_price(user_input[CONF_ENERGY_PRICE]))
                    existing = self.config_entry.options
                    if CONF_ENERGY_PRICE not in user_input and CONF_ENERGY_PRICE in existing:
                        encrypted[CONF_ENERGY_PRICE] = existing[CONF_ENERGY_PRICE]
                    periods = user_input.get(CONF_COST_PERIODS, existing.get(CONF_COST_PERIODS, []))
                    encrypted[CONF_COST_PERIODS] = validate_cost_periods(periods)
                    return self.async_create_entry(data=encrypted, title="Octopus Spain")
                errors["base"] = "invalid_auth"
            except CredentialError:
                errors["base"] = "secure_storage"
            except CostPeriodError:
                errors["base"] = "invalid_cost_periods"
            except ValueError:
                errors["base"] = "invalid_price"
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="init", data_schema=self._schema(), errors=errors)

    def _schema(self):
        price = self.config_entry.options.get(CONF_ENERGY_PRICE)
        price_key = vol.Optional(CONF_ENERGY_PRICE, default=price) if price is not None else vol.Optional(CONF_ENERGY_PRICE)
        return vol.Schema(
            {
                vol.Optional(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
                vol.Optional(CONF_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                price_key: NumberSelector(NumberSelectorConfig(min=0, max=1000, step="any", mode="box")),
                vol.Optional(CONF_COST_PERIODS, default=self.config_entry.options.get(CONF_COST_PERIODS, [])): ObjectSelector({
                    "multiple": True,
                    "label_field": "start",
                    "fields": {
                        "start": {"label": "Desde / From", "required": True, "selector": DateSelector()},
                        **{key: {"label": label, "required": True, "selector": NumberSelector(NumberSelectorConfig(min=0, max=maximum, step="any", mode="box"))}
                           for key, label, maximum in [
                               ("energy_price", "Energía sin impuestos / Energy excl. tax (€/kWh)", 1000),
                               ("power_per_day", "Potencia sin impuestos / Power excl. tax (€/día)", 1000),
                               ("rental_per_day", "Alquiler sin impuestos / Rental excl. tax (€/día)", 1000),
                               ("electricity_tax_percent", "Impuesto eléctrico / Electricity tax (%)", 100),
                               ("vat_percent", "IVA / VAT (%)", 100),
                           ]},
                    },
                }),
            }
        )
