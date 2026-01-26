DEFAULT_CONFIG = {
    "picobridge": {
        "version": "0.1",
        "plugged_device": "",
        "location": "",
        "port": 2222,
        "wlan": {
            "is_ad_hoc": True,
            "ad_hoc": {"ssid": "PicoBridge", "psk": "pico1234"},
            "infrastructure": {"ssid": "", "psk": ""}
        },
        "uart": {
            "physical": {"uart_id": 0, "tx_gp": 0, "rx_gp": 1},
            "settings": {"baudrate": 9600, "bits": 8, "parity": None, "stop": 1}
        },
        "display": {"i2c": {"id": 1, "sda_gp": 18, "scl_gp": 19}},
        "screensaver": {"enabled": True, "timeout_s": 30},
        "webservice": {"port": 8080}
    }
}