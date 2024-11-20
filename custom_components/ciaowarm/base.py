import asyncio
import aiohttp

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import (
    DOMAIN,
    LOGGER,
    REQUEST_URL_PREFIX,
)


class XiaowoEntity(Entity):
    """Xiaowo base device."""

    def __init__(self, device_id) -> None:
        self._attr_unique_id = f"xiaowo.{device_id}"
        self._device_id = device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
        )

    async def _send_command(self, device, option_key, option_value) -> bool:
        """Send command to the device."""
        _device_info_url = REQUEST_URL_PREFIX + "/ciaowarm/hass/v1/device/info"
        try:
            headers = {'token': device.token}
            data = {
                'phone': device.phone,
                'gateway_id': device.gateway_id,
                'thermostat_id': device.thermostat_id,
                'boiler_id': device.boiler_id,
                'option_key': option_key,
                'option_value': option_value
            }
            async with aiohttp.ClientSession() as session:
                async with session.put(_device_info_url, data=data, headers=headers) as response:
                    json_data = await response.json()
                    if json_data is not None:
                        message_code = json_data["message_code"]
                        if message_code == 0:
                            return True
                        else:
                            LOGGER.error("json_data: %s", str(json_data["message_info"]))
                    else:
                        LOGGER.error("请求失败！")
        except(asyncio.TimeoutError, aiohttp.ClientError):
            LOGGER.error("Error while accessing: %s", _device_info_url)
        return False
