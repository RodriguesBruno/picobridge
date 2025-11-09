

class Logger:
    def __init__(self, name=None) -> None:
        self.name = name or "root"

    def debug(self, msg: str) -> None:
        print(f"[DEBUG] {self.name}: {msg}")

    def info(self, msg: str) -> None:
        print(f"[INFO] {self.name}: {msg}")

    def warning(self, msg: str) -> None:
        print(f"[WARNING] {self.name}: {msg}")

    def error(self, msg: str) -> None:
        print(f"[ERROR] {self.name}: {msg}")

    def critical(self, msg) -> None:
        print(f"[CRITICAL] {self.name}: {msg}")
