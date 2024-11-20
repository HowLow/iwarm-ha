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
    CONF_KEY
)


class XiaowoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Xiaowo Config Flow."""

    async def async_step_user(self, user_input=None):
        """Step user."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            _device_info_url = REQUEST_URL_PREFIX + "/ciaowarm/hass/v1/account/check?phone=" + user_input[CONF_PHONE]
            try:
                headers = {'token': user_input[CONF_KEY]}
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(_device_info_url) as response:
                        json_data = await response.json()
                        if json_data is not None:
                            message_code = json_data["message_code"]
                            if message_code == 0:
                                phone = user_input[CONF_PHONE]
                                key = user_input[CONF_KEY]
                                data = {
                                    CONF_PHONE: phone,
                                    CONF_KEY: key
                                }
                                return self.async_create_entry(
                                    title=user_input[CONF_PHONE],
                                    data=data,
                                )
                            else:
                                LOGGER.error("json_data: %s", json_data)
                                errors["base"] = json_data["message_info"]
                        else:
                            errors["base"] = "请求失败！"
            except(asyncio.TimeoutError, aiohttp.ClientError):
                LOGGER.error("Error while accessing: %s", _device_info_url)

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PHONE, default=user_input.get(CONF_PHONE, ""), description="请输入手机号码"
                    ): str,
                    vol.Required(
                        CONF_KEY, default=user_input.get(CONF_KEY, ""), description="请输入授权码"
                    ): str
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
