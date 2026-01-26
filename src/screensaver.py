
class Screensaver:
    def __init__(self, enabled: bool, timeout_s: int = 10) -> None:
        self._enabled: bool = enabled
        self._timeout_s: int = timeout_s
        self._is_active: bool = False

    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_active(self) -> bool:
        return self._is_active

    def activate(self) -> None:
        self._is_active = True

    def deactivate(self) -> None:
        self._is_active = False

    def get_timeout(self) -> int:
        return self._timeout_s

    def set_timeout(self, value: int) -> None:
        if value <= 0:
            raise ValueError('Timeout value must be higher than 0')

        self._timeout_s = value

    def get_config(self) -> dict:
        return {
            "enabled": self._enabled,
            "timeout_s": self._timeout_s
        }
