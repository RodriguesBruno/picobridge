import json
import time
import asyncio
from machine import UART, Pin, reset
from network import WLAN

from src.file_handlers import read_file_as_json, write_file_as_json
from src.system_monitor import SystemMonitor
from src.telnet import telnet_negotiation
from src.wlan import start_ap, wifi_connect


def apply_backspaces(s: str) -> str:
    """Apply terminal-style backspaces to a string efficiently."""
    out = []
    for ch in s:
        if ch == '\b':
            if out:
                out.pop()
        else:
            out.append(ch)

    return ''.join(out)


def normalize_newlines(s: str) -> str:
    """Normalize CRLF to LF and drop stray CR."""
    # Fast path: common CRLF -> LF
    s = s.replace('\r\n', '\n')
    # Drop any remaining lone \r (Cisco rarely uses lone CR for carriage return)
    s = s.replace('\r', '\n')

    return s


class PicoBridge:
    def __init__(self, config_path: str = 'config.json') -> None:
        self._config_path: str = config_path
        self._config: dict = read_file_as_json(config_path)

        # State
        self.clients = []
        self.websockets = []
        self._ws_buffer: str = ''

        self._tx_activity: bool = False
        self._rx_activity: bool = False

        self._rx_bytes: int = 0
        self._tx_bytes: int = 0
        self._last_stats_time = time.ticks_ms()
        self._rx_rate: int = 0
        self._tx_rate: int = 0

        self._utf8_tail: bytes = b''
        self._line_accum: str = ''
        self._last_rx_ms = time.ticks_ms()
        self._idle_flush_ms: int = 150

        self._WS_BATCH_TIME_MS: int = 60
        self._ws_batch_deadline = time.ticks_add(time.ticks_ms(), self._WS_BATCH_TIME_MS)

        self._flush_tokens = ('Username:', 'Password:', 'login:', '--More--')

        # Setup PluggedDevice/Location
        self._plugged_device: str = self._config.get('picobridge').get('plugged_device', "")
        self._location: str = self._config.get('picobridge').get('location', "")
        self._version: str = self._config.get('picobridge').get('version')

        # Setup WLAN
        self._wlan: WLAN | None = None
        self._ip_address: str | None = None
        self._is_ad_hoc: bool = self._config.get('picobridge').get('wlan').get('is_ad_hoc')
        self._tcp_port: int = self._config.get('picobridge').get('port')

        self._led: Pin = Pin("LED", Pin.OUT)

        # Init UART
        self._uart = UART or None

        self._system_monitor: SystemMonitor = SystemMonitor()

        self._crlf_to_uart: bool = True
        self._uart_to_crlf: bool = False
        print(f"PicoBridge v{self._version}")

    def start_uart(self) -> None:
        uart_conf = self._config.get('picobridge').get('uart')
        physical = uart_conf.get('physical')
        settings = uart_conf.get('settings')

        self._uart: UART = UART(
            physical.get('uart_id'),
            baudrate=settings.get('baudrate'),
            bits=settings.get('bits'),
            parity=settings.get('parity'),
            stop=settings.get('stop'),
            tx=Pin(physical.get('tx_pin')),
            rx=Pin(physical.get('rx_pin')),
            timeout=100,
            timeout_char=20
        )

    async def update_settings(self, new_settings: dict) -> None:
        must_save_config: list[bool] = []
        must_restart: bool = False

        plugged_device = new_settings.get('plugged_device')
        if self._plugged_device != plugged_device:
            self._config['picobridge']['plugged_device'] = plugged_device
            self._plugged_device = plugged_device
            must_save_config.append(True)

        location = new_settings.get('location')
        if self._location != location:
            self._config['picobridge']['location'] = location
            self._location = location
            must_save_config.append(True)

        uart_settings: dict = {
            'baudrate': new_settings.get('baudrate'),
            'bits': new_settings.get('bits'),
            'parity': new_settings.get('parity'),
            'stop': new_settings.get('stop')
        }

        if self._config['picobridge']['uart']['settings'] != uart_settings:
            self._config['picobridge']['uart']['settings'] = uart_settings

            self.start_uart()

            must_save_config.append(True)

        wlan_settings: dict = new_settings.get('wlan')

        if self._config.get('picobridge').get('wlan') != wlan_settings:
            self._config['picobridge']['wlan'] = wlan_settings

            must_save_config.append(True)
            must_restart = True

        if any(must_save_config):
            self.save_config()

        if must_restart:
            sleep_time: int = 5
            print(f"PicoBridge Network Settings changed. Restarting in {sleep_time}s")
            await asyncio.sleep(sleep_time)
            reset()


    def get_settings(self) -> dict:
        settings: dict = self._config.get('picobridge').get('uart').get('settings').copy()
        settings['wlan'] = self._config.get('picobridge').get('wlan').copy()
        settings['plugged_device'] = self._plugged_device
        settings['location'] = self._location

        return settings

    def get_version(self) -> str:
        return self._version

    def save_config(self) -> None:
        write_file_as_json(self._config_path, self._config)

    def get_tcp_port(self) -> int:
        return self._tcp_port

    def get_ip_address(self) -> str:
        return self._ip_address

    def start_network(self) -> None:
        if self._is_ad_hoc:
            wlan_conf = self._config.get('picobridge').get('wlan').get('ad_hoc')
            print("Starting Network mode: Access Point")
            self._wlan: WLAN = start_ap(ssid=wlan_conf.get('ssid'), password=wlan_conf.get('psk'))
        else:
            try:
                wlan_conf = self._config.get('picobridge').get('wlan').get('infrastructure')
                print("Starting Network mode: Infrastructure")
                self._wlan = wifi_connect(ssid=wlan_conf.get('ssid'), password=wlan_conf.get('psk'))

            except Exception:
                print("WLAN was reset back to AD HOC mode")

                self._config['picobridge']['wlan']['is_ad_hoc'] = True
                self._is_ad_hoc = True
                self.save_config()

                self.start_network()

        self._ip_address = self._wlan.ifconfig()[0]

    def register_websocket(self, ws) -> None:
        self.websockets.append(ws)

    def unregister_websocket(self, ws) -> None:
        if ws in self.websockets:
            self.websockets.remove(ws)

    def broadcast_uart_activity(self) -> None:
        data = json.dumps({'tx': self._tx_activity, 'rx': self._rx_activity})
        for ws in self.websockets[:]:
            try:
                await ws.send(data)

            except:
                self.websockets.remove(ws)

    def wake_uart(self) -> None:
        """Send a wake-up signal (RETURN) to UART to trigger login banner or prompt."""
        try:
            if self._uart:
                self._uart.write(b'\r')

        except Exception as e:
            print(f"[Wake UART Error] {e}")

    def _utf8_feed(self, chunk: bytes) -> str:
        """
        Incrementally decode UTF-8 from bytes. Keeps up to 3 trailing bytes
        if they form an incomplete UTF-8 sequence (no errors='ignore' needed).
        """
        b = self._utf8_tail + chunk
        # try full decode first
        try:
            s = b.decode()
            self._utf8_tail = b''

            return s

        except:
            # try dropping 1..3 tail bytes as possible incomplete sequence
            for keep in (1, 2, 3):
                if len(b) > keep:
                    try:
                        s = b[:-keep].decode()
                        self._utf8_tail = b[-keep:]
                        return s

                    except:
                        pass

            # if still nothing decodes, keep all bytes as tail (avoid data loss)
            self._utf8_tail = b

            return ''

    def _split_on_pager_or_prompt(self, text: str):
        """
        Detect tokens like '--More--', 'Username:' etc. If present, split the text
        so that token is emitted as its own 'line' (with newline).
        Returns: (prefix, token_or_None, suffix)
        """
        first_idx = -1
        first_tok = None
        for tok in self._flush_tokens:
            idx = text.find(tok)
            if idx != -1 and (first_idx == -1 or idx < first_idx):
                first_idx = idx
                first_tok = tok

        if first_idx == -1:
            return text, None, ''

        prefix = text[:first_idx]
        suffix = text[first_idx + len(first_tok):]

        return prefix, first_tok, suffix

    def _frames_from_text(self, s: str) -> list:
        """
        Core framing logic. Feed decoded+cleaned text here.
        Emits a list of frames (strings) to send to the browser.
        Conditions to emit:
          - newline -> emit that line
          - pager/prompt token -> emit preceding text (if any) + token on its own line
        """
        frames = []

        # handle backspaces and newlines
        s = apply_backspaces(s)
        s = normalize_newlines(s)

        # accumulate into current line buffer
        self._line_accum += s

        # 1) split by newline and emit complete lines
        while True:
            nl = self._line_accum.find('\n')
            if nl == -1:
                break
            line = self._line_accum[:nl + 1]  # include newline
            frames.append(line)
            self._line_accum = self._line_accum[nl + 1:]

        # 2) detect pager/prompt tokens in remaining partial
        #    emit them IMMEDIATELY as their own frames
        while True:
            if not self._line_accum:
                break

            before, tok, after = self._split_on_pager_or_prompt(self._line_accum)

            if tok is None:
                break

            if before:
                # emit text before token as a "line"
                frames.append(before + ('\n' if not before.endswith('\n') else ''))

            # emit the token on its own line
            frames.append(tok + '\n')
            self._line_accum = after

        return frames

    def _process_uart_chunk(self, chunk: bytes) -> list:
        """
        Ingest raw UART bytes, produce a list of frames to send to the browser.
        """
        self._last_rx_ms = time.ticks_ms()
        decoded = self._utf8_feed(chunk)

        if not decoded:
            return []

        return self._frames_from_text(decoded)

    def _flush_uart_idle(self) -> list:
        """
        If we've been idle and still have a partial line/prompt, emit it.
        This prevents prompts like 'Username:' from getting stuck.
        """
        now = time.ticks_ms()
        if self._line_accum and time.ticks_diff(now, self._last_rx_ms) >= self._idle_flush_ms:
            frame = self._line_accum
            self._line_accum = ''

            return [frame]

        return []

    async def uart_to_clients(self, stop_flag: list[bool]) -> None:
        while not stop_flag[0]:
            had_data = False

            if self._uart.any():
                data: bytes = self._uart.read(self._uart.any())
                if data:
                    had_data = True
                    self._rx_bytes += len(data)

                    if self._uart_to_crlf:
                        data = data.replace(b'\n', b'\r\n')

                    self._led.on()
                    self._rx_activity = True

                    # 1) forward raw bytes to TCP clients (unchanged behavior)
                    for client in self.clients[:]:
                        try:
                            client.write(data)
                            await client.drain()

                        except:
                            self.clients.remove(client)

                    # 2) frame nicely for the WebSocket terminal
                    frames = self._process_uart_chunk(data)
                    if frames:
                        payloads = [json.dumps({"output": f}) for f in frames]
                        for ws in self.websockets[:]:
                            try:
                                for p in payloads:
                                    await ws.send(p)

                            except:
                                self.websockets.remove(ws)

                    self._led.off()

            # If no new data, check idle flush to push prompts/partials
            if not had_data:
                frames = self._flush_uart_idle()
                if frames:
                    payloads = [json.dumps({"output": f}) for f in frames]
                    for ws in self.websockets[:]:
                        try:
                            for p in payloads:
                                await ws.send(p)

                        except:
                            self.websockets.remove(ws)

                await asyncio.sleep(0.005)

    async def client_to_uart(self, reader, writer, stop_flag: list[bool]) -> None:
        try:
            while not stop_flag[0]:
                buf = await reader.read(256)
                if not buf:
                    break

                if b'\xff' in buf:
                    buf, reply = telnet_negotiation(buf)
                    if reply:
                        try:
                            writer.write(reply)
                            await writer.drain()

                        except:
                            pass

                if not buf:
                    continue

                self._tx_activity = True

                for b in buf:
                    self._tx_bytes += 1
                    if b in (0x0A, 0x0D):
                        if self._crlf_to_uart:
                            self._uart.write(b'\r')
                    else:
                        self._uart.write(bytes([b]))
                        await asyncio.sleep(0.005)

        finally:
            stop_flag[0] = True

    async def broadcast_uart_loop(self) -> None:
        while True:
            if self._tx_activity or self._rx_activity:
                data: str = json.dumps({'tx': self._tx_activity, 'rx': self._rx_activity})
                self._tx_activity = False
                self._rx_activity = False

                for ws in self.websockets[:]:
                    try:
                        await ws.send(data)

                    except:
                        self.websockets.remove(ws)

            await asyncio.sleep(0.05)

    async def monitor_throughput(self) -> None:
        while True:
            await asyncio.sleep(1)

            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, self._last_stats_time) / 1000  # in seconds
            self._last_stats_time = now

            self._rx_rate = int(self._rx_bytes / elapsed)
            self._tx_rate = int(self._tx_bytes / elapsed)

            self._rx_bytes = 0
            self._tx_bytes = 0

            data = json.dumps({'rx_bps': self._rx_rate, 'tx_bps': self._tx_rate})

            for ws in self.websockets[:]:
                try:
                    await ws.send(data)

                except:
                    self.websockets.remove(ws)

    async def monitor_system(self) -> None:
        while True:
            await asyncio.sleep(1)

            mem_free = self._system_monitor.get_mem_free()
            mem_alloc = self._system_monitor.get_mem_alloc()

            data = json.dumps({'mem_free': mem_free, 'mem_alloc': mem_alloc})

            for ws in self.websockets[:]:
                try:
                    await ws.send(data)

                except:
                    self.websockets.remove(ws)

    async def handle_websocket_input(self, raw_json: str) -> None:
        try:
            message = json.loads(raw_json)

            if 'input' in message:
                command = message.get('input')
                if self._crlf_to_uart:
                    command += '\r'

                encoded = command.encode('utf-8')

                self._tx_activity = True
                self._tx_bytes += len(encoded)

                self._uart.write(encoded)

        except Exception as e:
            print(f"[WebSocket Input Error] {e}")

    def enable_uart_to_crlf(self) -> None:
        self._uart_to_crlf = True

    def disable_uart_to_crlf(self) -> None:
        self._uart_to_crlf = False

    def enable_crlf_to_uart(self) -> None:
        self._crlf_to_uart = True

    def disable_crlf_to_uart(self) -> None:
        self._crlf_to_uart = False
