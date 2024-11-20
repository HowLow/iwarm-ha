"""Config flow for Ciaowarm."""
from __future__ import annotations
import asyncio
import aiohttp

from homeassistant import config_entries
import voluptuous as vol

from .const import (
    DOMAIN,
    LOGGER,
    REQUEST_URL_PREFIX,
    CONF_PHONE,
    CONF_KEY,
)


class XiaowoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Xiaowo Config Flow."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            phone = user_input[CONF_PHONE]
            key = user_input[CONF_KEY]
            _device_info_url = f"{REQUEST_URL_PREFIX}/ciaowarm/hass/v1/account/check?phone={phone}"

            try:
                headers = {'token': key}
                timeout = aiohttp.ClientTimeout(total=10)

                async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                    async with session.get(_device_info_url) as response:
                        if response.status != 200:
                            LOGGER.error("HTTP error: %s - %s", response.status, await response.text())
                            errors["base"] = "cannot_connect"
                        else:
                            try:
                                json_data = await response.json()
                            except ValueError:
                                LOGGER.error("Invalid JSON response.")
                                errors["base"] = "invalid_response"
                                json_data = None

                            if json_data and "message_code" in json_data:
                                if json_data["message_code"] == 0:
                                    # Successful validation
                                    return self.async_create_entry(
                                        title=phone,
                                        data={
                                            CONF_PHONE: phone,
                                            CONF_KEY: key,
                                        },
                                    )
                                else:
                                    LOGGER.error("API error: %s", json_data)
                                    errors["base"] = "invalid_credentials"
                            else:
                                errors["base"] = "unexpected_response"

            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                LOGGER.error("Error connecting to API: %s", str(e))
                errors["base"] = "cannot_connect"

        # Default values for the form
        user_input = user_input or {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PHONE, default=user_input.get(CONF_PHONE, "")): str,
                    vol.Required(CONF_KEY, default=user_input.get(CONF_KEY, "")): str,
                }
            ),
            errors=errors,
        )
