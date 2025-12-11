import asyncio
import time
import network

from network import WLAN


async def wlan_infra_mode(ssid: str, password: str, max_wait_s: int = 60, *, display_callback, force_reconnect: bool = True) -> WLAN:
    """
    Connect to Wi-Fi and raise RuntimeError if not connected within max_wait_s.
    Also raises immediately for known failure statuses.
    """
    if not callable(display_callback):
        raise ValueError("display_callback must be an async callable")

    msg = f'SSID: {ssid}'
    await display_callback(line=2, text=msg)
    await display_callback(line=3, text='')

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if force_reconnect and wlan.isconnected():
        try:
            wlan.disconnect()

        except AttributeError:
            pass

        await asyncio.sleep(0.1)

    wlan.connect(ssid, password)
    t0 = time.ticks_ms()

    # Status codes per MicroPython: <0 = failure, 0 idle, 1 connecting, 3 got IP
    while True:
        s = wlan.status()
        if s < 0:
            msg = f"WiFi failed (status {s}) while connecting to '{ssid}'"
            raise Exception(msg)

        if s >= 3 or wlan.isconnected():  # STAT_GOT_IP (3) or equivalent
            mac_bytes = wlan.config('mac')
            mac_str = '.'.join(
                '{:02x}{:02x}'.format(mac_bytes[i], mac_bytes[i + 1])
                for i in range(0, 6, 2)
            )
            msg = f"Connected w/MAC: {mac_str}"
            print(msg)

            await display_callback(line=2, text=msg[0:15])
            await display_callback(line=3, text=msg[17:])
            await display_callback(line=5, text=wlan.ifconfig()[0])

            await asyncio.sleep(6)

            lines_to_clear = (2, 3, 4, 5)
            for line in lines_to_clear:
                await display_callback(line=line, text='')

            return wlan

        if time.ticks_diff(time.ticks_ms(), t0) >= max_wait_s * 1000:
            try:
                wlan.disconnect()

            except AttributeError:
                pass

            msg = f"WiFi connection to '{ssid}' timed out after {max_wait_s} seconds"

            raise Exception(msg)

        await asyncio.sleep_ms(250)


async def wlan_ap_mode(ssid: str, password: str) -> WLAN:
    ap: WLAN = network.WLAN(network.AP_IF)
    ap.config(essid=ssid, password=password)
    ap.active(True)

    print("Starting Access Point...")
    while not ap.active():
        time.sleep(0.1)

    print("Access Point active")
    print("Network config:", ap.ifconfig())

    return ap
