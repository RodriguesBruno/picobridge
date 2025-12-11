import gc
import asyncio


class SystemMonitor:
    def __init__(self, errors_max_qty: int = 1_000, refresh_timer: int = 1) -> None:
        self._refresh_timer: int = refresh_timer
        self._mem_free = 0
        self._mem_alloc = 0
        self._mem_low_value = 70_000
        self._mem_refresh_timer: int = 1
        self._gc_timer: int = 5
        self._errors_qty: int = 0
        self._errors_max_qty: int = errors_max_qty
        self._start_date: str = ''
        self._loop = asyncio.get_event_loop()

        self._refresh()
        gc.enable()

    def _refresh(self) -> None:
        self._loop.create_task(self._update_memory())
        self._loop.create_task(self._run_garbage_collector())

    async def get_dict(self) -> dict:
        return {
            "mem_free": self._mem_free,
            "mem_alloc": self._mem_alloc,
            "mem_low_value": self._mem_low_value,
            "mem_refresh_timer": self._mem_refresh_timer,
            "gc_timer": self._gc_timer,
            "errors_qty": self._errors_qty,
            "errors_max_qty": self._errors_max_qty,
            "start_date": self._start_date
        }

    def get_mem_low_value(self) -> int:
        return self._mem_low_value

    def set_mem_low_value(self, value: int) -> None:
        self._mem_low_value = value

    def get_mem_refresh_timer(self) -> int:
        return self._mem_refresh_timer

    def set_mem_refresh_timer(self, value: int) -> None:
        self._mem_refresh_timer = value

    def set_gc_timer(self, value: int) -> None:
        self._gc_timer = value

    def get_mem_free(self) -> int:
        return self._mem_free

    def get_mem_alloc(self) -> int:
        return self._mem_alloc

    def get_errors_qty(self) -> int:
        return self._errors_qty

    def set_errors_qty(self, value: int) -> None:
        self._errors_qty = value

    def set_errors_max_qty(self, value: int) -> None:
        self._errors_max_qty = value

    def has_too_many_errors(self) -> bool:
        return self._errors_qty >= self._errors_max_qty

    def set_start_date(self, date: str) -> None:
        self._start_date = date

    def get_start_date(self) -> str:
        return self._start_date

    async def _run_garbage_collector(self) -> None:
        while True:
            if self._mem_free < self._mem_low_value:
                gc.collect()

            await asyncio.sleep(self._gc_timer)

    async def _update_memory(self) -> None:
        while True:
            self._mem_free = int(gc.mem_free())
            self._mem_alloc = int(gc.mem_alloc())

            await asyncio.sleep(self._mem_refresh_timer)
