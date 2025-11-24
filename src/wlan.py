import network
import utime as time
from network import WLAN


def wlan_infra_mode(ssid: str, password: str, max_wait_s: int = 60, *, force_reconnect: bool = True) -> WLAN:
    """
    Connect to Wi-Fi and raise RuntimeError if not connected within max_wait_s.
    Also raises immediately for known failure statuses.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if force_reconnect and wlan.isconnected():
        try:
            wlan.disconnect()

        except AttributeError:
            pass

        time.sleep(0.1)

    wlan.connect(ssid, password)
    t0 = time.ticks_ms()

    # Status codes per MicroPython: <0 = failure, 0 idle, 1 connecting, 3 got IP
    while True:
        s = wlan.status()
        if s < 0:
            raise Exception(f"WiFi failed (status {s}) while connecting to '{ssid}'")

        if s >= 3 or wlan.isconnected():  # STAT_GOT_IP (3) or equivalent
            mac_bytes = wlan.config('mac')
            mac_str = ':'.join('{:02x}'.format(b) for b in mac_bytes)
            print("Connected with MAC:", mac_str)

            return wlan

        if time.ticks_diff(time.ticks_ms(), t0) >= max_wait_s * 1000:
            try:
                wlan.disconnect()

            except AttributeError:
                pass

            raise Exception(f"WiFi connection to '{ssid}' timed out after {max_wait_s} seconds")

        time.sleep(0.25)


def wlan_ap_mode(ssid: str, password: str) -> WLAN:
    ap: WLAN = network.WLAN(network.AP_IF)
    ap.config(essid=ssid, password=password)
    ap.active(True)

    print("Starting Access Point...")
    while not ap.active():
        time.sleep(0.1)

    print("Access Point active")
    print("Network config:", ap.ifconfig())

    return ap
