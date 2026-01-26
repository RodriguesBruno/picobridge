import json

from src.file_handlers import read_file_as_json

DEFAULT_CONFIG = {
    "picobridge": {
        "version": "1.6",
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

def _deep_update(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_update(dst[k], v)
        else:
            dst[k] = v
    return dst

def load_config(filename: str) -> dict:
    config = read_file_as_json(filename, default={})
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    _deep_update(merged, config)
    return merged