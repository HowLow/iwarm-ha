import asyncio
import aiohttp
import homeassistant.util.dt as dt_util

from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    LOGGER,
    REQUEST_URL_PREFIX,
    CONF_PHONE,
    CONF_KEY,
    XiaowoDevice, XiaowoThermostat, XiaowoBoiler, XiaowoExtBoiler
)

GATEWAY_PLATFORMS = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

WEATHER_TIME_BETWEEN_UPDATES = timedelta(seconds=20)


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})
    phone = entry.data[CONF_PHONE]
    access_token = entry.data[CONF_KEY]
    _device_info_url = REQUEST_URL_PREFIX + "/ciaowarm/hass/v1/device/info?phone=" + phone
    try:
        device_registry = dr.async_get(hass)
        headers = {'token': access_token}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(_device_info_url) as response:
                json_data = await response.json()
                message_code = json_data["message_code"]
                message_info = json_data["message_info"]
                if message_code != 0:
                    LOGGER.error("Error interface return: %s", message_info)
                    return False

                device_list: list[XiaowoDevice] = []
                for item in message_info:
                    gateway_id = item['gateway_id']
                    for gatewayItem in item:
                        if gatewayItem == "thermostats":
                            thermostats = item[gatewayItem]
                            for thermostat in thermostats:
                                device_list.append(XiaowoThermostat(phone, access_token, gateway_id, thermostat))
                                thermostat_id = "t" + str(thermostat["thermostat_id"])
                                device_registry.async_get_or_create(
                                    config_entry_id=entry.entry_id,
                                    identifiers={(DOMAIN, thermostat_id)},
                                    manufacturer="IWARM TECH CO., LTD.",
                                    name=thermostat["thermostat_name"],
                                    model=f"thermostat",
                                )
                        if gatewayItem == "boilers":
                            boilers = item[gatewayItem]
                            for boiler in boilers:
                                device_list.append(XiaowoBoiler(phone, access_token, gateway_id, boiler))
                                boiler_id = "b" + str(boiler["boiler_id"])
                                device_registry.async_get_or_create(
                                    config_entry_id=entry.entry_id,
                                    identifiers={(DOMAIN, boiler_id)},
                                    manufacturer="IWARM TECH CO., LTD.",
                                    name="小沃壁挂炉",
                                    model=f"boiler",
                                )
                        if gatewayItem == "extBoiler":
                            ext_boiler = item[gatewayItem]
                            device_list.append(XiaowoExtBoiler(phone, access_token, gateway_id, ext_boiler))
                            ext_boiler_id = "e" + str(gateway_id)
                            device_registry.async_get_or_create(
                                config_entry_id=entry.entry_id,
                                identifiers={(DOMAIN, ext_boiler_id)},
                                manufacturer="IWARM TECH CO., LTD.",
                                name="第三方壁挂炉",
                                model=f"extBoiler",
                            )

        device_data = HomeAssistantXiaowoData(phone, access_token, device_list)
        await device_data.async_update(dt_util.now())
        async_track_time_interval(hass, device_data.async_update, WEATHER_TIME_BETWEEN_UPDATES)
        hass.data[DOMAIN][entry.entry_id] = device_data

        await hass.config_entries.async_forward_entry_setups(entry, GATEWAY_PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(update_listener))

    except(asyncio.TimeoutError, aiohttp.ClientError):
        LOGGER.error("Error while accessing: %s", _device_info_url)
        return False

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class HomeAssistantXiaowoData:
    """Xiaowo data stored in the Home Assistant data object."""

    def __init__(self, phone, access_token, device_list):
        self._phone = phone
        self._access_token = access_token
        self._device_info_url = REQUEST_URL_PREFIX + "/ciaowarm/hass/v1/device/info?phone=" + phone
        self._headers = {'token': access_token}
        self.device_list: list[XiaowoDevice] = device_list

    async def async_update(self, now):
        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.get(self._device_info_url) as response:
                json_data = await response.json()
                message_code = json_data["message_code"]
                message_info = json_data["message_info"]
                if message_code != 0:
                    LOGGER.error("Error interface return: %s", message_info)
                    return False
                for item in message_info:
                    gateway_id = item['gateway_id']
                    for gatewayItem in item:
                        if gatewayItem == "thermostats":
                            thermostats = item[gatewayItem]
                            for thermostat in thermostats:
                                if self.device_list:
                                    for device in self.device_list:
                                        if isinstance(device, XiaowoThermostat):
                                            if device.thermostat_id == thermostat['thermostat_id']:
                                                device.update(thermostat)
                        if gatewayItem == "boilers":
                            boilers = item[gatewayItem]
                            for boiler in boilers:
                                if self.device_list:
                                    for device in self.device_list:
                                        if isinstance(device, XiaowoBoiler):
                                            if device.boiler_id == boiler['boiler_id']:
                                                device.update(boiler)
                        if gatewayItem == "extBoiler":
                            ext_boiler = item[gatewayItem]
                            if self.device_list:
                                for device in self.device_list:
                                    if isinstance(device, XiaowoExtBoiler):
                                        if device.gateway_id == gateway_id:
                                            device.update(ext_boiler)
