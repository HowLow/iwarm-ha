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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xiaowo integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    phone = entry.data.get(CONF_PHONE)
    access_token = entry.data.get(CONF_KEY)

    if not phone or not access_token:
        LOGGER.error("Missing required configuration parameters.")
        return False

    _device_info_url = f"{REQUEST_URL_PREFIX}/ciaowarm/hass/v1/device/info?phone={phone}"

    try:
        device_registry = dr.async_get(hass)
        headers = {'token': access_token}
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(_device_info_url) as response:
                if response.status != 200:
                    LOGGER.error("HTTP error: %s - %s", response.status, await response.text())
                    return False

                try:
                    json_data = await response.json()
                except ValueError as e:
                    LOGGER.error("Error parsing JSON response: %s", str(e))
                    return False

                if not json_data or "message_code" not in json_data or "message_info" not in json_data:
                    LOGGER.error("Unexpected JSON structure: %s", json_data)
                    return False

                if json_data["message_code"] != 0:
                    LOGGER.error("Error from API: %s", json_data["message_info"])
                    return False

                device_list: list[XiaowoDevice] = []
                for item in json_data["message_info"]:
                    gateway_id = item['gateway_id']
                    for gateway_item in item:
                        if gateway_item == "thermostats":
                            thermostats = item[gateway_item]
                            for thermostat in thermostats:
                                device_list.append(XiaowoThermostat(phone, access_token, gateway_id, thermostat))
                                thermostat_id = "t" + str(thermostat["thermostat_id"])
                                device_registry.async_get_or_create(
                                    config_entry_id=entry.entry_id,
                                    identifiers={(DOMAIN, thermostat_id)},
                                    manufacturer="IWARM TECH CO., LTD.",
                                    name=thermostat["thermostat_name"],
                                    model="thermostat",
                                )
                        elif gateway_item == "boilers":
                            boilers = item[gateway_item]
                            for boiler in boilers:
                                device_list.append(XiaowoBoiler(phone, access_token, gateway_id, boiler))
                                boiler_id = "b" + str(boiler["boiler_id"])
                                device_registry.async_get_or_create(
                                    config_entry_id=entry.entry_id,
                                    identifiers={(DOMAIN, boiler_id)},
                                    manufacturer="IWARM TECH CO., LTD.",
                                    name="小沃壁挂炉",
                                    model="boiler",
                                )
                        elif gateway_item == "extBoiler":
                            ext_boiler = item[gateway_item]
                            device_list.append(XiaowoExtBoiler(phone, access_token, gateway_id, ext_boiler))
                            ext_boiler_id = "e" + str(gateway_id)
                            device_registry.async_get_or_create(
                                config_entry_id=entry.entry_id,
                                identifiers={(DOMAIN, ext_boiler_id)},
                                manufacturer="IWARM TECH CO., LTD.",
                                name="第三方壁挂炉",
                                model="extBoiler",
                            )

        # Store device data and set up periodic updates
        device_data = HomeAssistantXiaowoData(phone, access_token, device_list)
        await device_data.async_update(dt_util.now())
        async_track_time_interval(hass, device_data.async_update, WEATHER_TIME_BETWEEN_UPDATES)
        hass.data[DOMAIN][entry.entry_id] = device_data

        # Set up platforms
        await hass.config_entries.async_forward_entry_setups(entry, GATEWAY_PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(update_listener))

    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
        LOGGER.error("Error while accessing: %s, %s", _device_info_url, str(e))
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
        self._device_info_url = f"{REQUEST_URL_PREFIX}/ciaowarm/hass/v1/device/info?phone={phone}"
        self._headers = {'token': access_token}
        self.device_list: list[XiaowoDevice] = device_list

    async def async_update(self, now):
        """Fetch the latest data from the API."""
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(headers=self._headers, timeout=timeout) as session:
                async with session.get(self._device_info_url) as response:
                    if response.status != 200:
                        LOGGER.error("HTTP error during update: %s - %s", response.status, await response.text())
                        return False

                    try:
                        json_data = await response.json()
                    except ValueError as e:
                        LOGGER.error("Error parsing JSON response during update: %s", str(e))
                        return False

                    if not json_data or "message_code" not in json_data or "message_info" not in json_data:
                        LOGGER.error("Unexpected JSON structure during update: %s", json_data)
                        return False

                    if json_data["message_code"] != 0:
                        LOGGER.error("Error from API during update: %s", json_data["message_info"])
                        return False

                    # Update devices
                    for item in json_data["message_info"]:
                        gateway_id = item['gateway_id']
                        for gateway_item in item:
                            if gateway_item == "thermostats":
                                thermostats = item[gateway_item]
                                for thermostat in thermostats:
                                    for device in self.device_list:
                                        if isinstance(device, XiaowoThermostat) and device.thermostat_id == thermostat['thermostat_id']:
                                            device.update(thermostat)
                            elif gateway_item == "boilers":
                                boilers = item[gateway_item]
                                for boiler in boilers:
                                    for device in self.device_list:
                                        if isinstance(device, XiaowoBoiler) and device.boiler_id == boiler['boiler_id']:
                                            device.update(boiler)
                            elif gateway_item == "extBoiler":
                                ext_boiler = item[gateway_item]
                                for device in self.device_list:
                                    if isinstance(device, XiaowoExtBoiler) and device.gateway_id == gateway_id:
                                        device.update(ext_boiler)
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            LOGGER.error("Error while updating devices: %s", str(e))
