from src.logger import Logger


class WebsocketManager:
    def __init__(self) -> None:
        self._websockets: list = []
        self._logger: Logger = Logger("WebSocketManager")

    def register(self, ws) -> None:
        if ws not in self._websockets:
            self._websockets.append(ws)

    def unregister(self, ws) -> None:
        try:
            if ws in self._websockets:
                self._websockets.remove(ws)

        except Exception as e:
            if self._logger:
                self._logger.info(f"Error removing websocket: {e}")

    async def _safe_send(self, ws, payload: str) -> bool:
        try:
            await ws.send(payload)
            return True

        except Exception as e:
            if self._logger:
                self._logger.info(f"Websocket send failed, removing ws: {e}")

            try:
                self._websockets.remove(ws)

            except Exception:
                pass

            return False

    async def broadcast_payloads(self, payloads: list[str]) -> None:
        for ws in self._websockets[:]:
            for p in payloads:
                ok = await self._safe_send(ws, p)

                if not ok:
                    break
