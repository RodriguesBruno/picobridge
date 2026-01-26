import json
import time
import asyncio
from machine import UART, Pin, reset
from network import WLAN

from src.display_controller import DisplayController
from src.file_handlers import read_file_as_json, write_file_as_json
from src.terminal_framer import TerminalFramer
from src.websocket_manager import WebsocketManager
from src.system_monitor import SystemMonitor
from src.telnet import telnet_negotiation
from src.wlan import wlan_ap_mode, wlan_infra_mode
from src.logger import Logger
from src.default.config.default_config import DEFAULT_CONFIG


def _merge_defaults(cfg: dict, defaults: dict) -> dict:
    for k, v in defaults.items():
        if k not in cfg:
            cfg[k] = v

        elif isinstance(v, dict) and isinstance(cfg.get(k), dict):
            _merge_defaults(cfg[k], v)

    return cfg


class PicoBridge:
    def __init__(self, display_controller: DisplayController, ws_manager: WebsocketManager, config_path: str = 'config.json') -> None:
        self._terminal_framer: TerminalFramer = TerminalFramer()
        self._system_monitor: SystemMonitor = SystemMonitor()

        self._ws_manager: WebsocketManager = ws_manager
        self._config_path: str = config_path
        self._config = read_file_as_json(config_path, default=DEFAULT_CONFIG)
        self._config = _merge_defaults(self._config, DEFAULT_CONFIG)
        self._logger: Logger = Logger("[PicoBridge]")

        self._display_controller: DisplayController = display_controller

        # Identifier
        self._identify_active: bool = False
        self._identify_original_brightness: int = 255
        self._identify_task = None

        # State
        self.clients = []

        self._tx_activity: bool = False
        self._rx_activity: bool = False

        self._rx_bytes: int = 0
        self._tx_bytes: int = 0
        self._last_stats_time: int = time.ticks_ms()

        self._rx_rate: int = 0
        self._tx_rate: int = 0

        # Setup PluggedDevice/Location
        self._plugged_device: str = self._config.get('picobridge').get('plugged_device', "")
        self._location: str = self._config.get('picobridge').get('location', "")
        self._version: str = self._config.get('picobridge').get('version')
        self._web_service_port: int = self._config.get('picobridge', {}).get('webservice', {}).get('port', 8080)

        # Setup WLAN
        self._wlan: WLAN = None
        self._ip_address: str = '127.0.0.1'
        self._is_ad_hoc: bool = self._config.get('picobridge').get('wlan').get('is_ad_hoc')
        self._tcp_port: int = self._config.get('picobridge').get('port')
        self._wlan_restarts: int = 0
        self._wlan_max_restarts: int = 5
        self._reset_timer_due_to_wlan_error: int = 3

        self._led: Pin = Pin("LED", Pin.OUT)

        # Init UART
        self._uart = None
        self._crlf_to_uart: bool = True
        self._uart_to_crlf: bool = False

        self._logger.info(f"PicoBridge v{self._version} Starting")

    async def start(self) -> None:
        await self._system_monitor.start()
        asyncio.create_task(self._monitor_system())

        await self._display_controller.start()
        await self._display_controller.add_highlight(line=1)
        await self._display_controller.write_to_line(line=1, text=f"PicoBridge")
        await self.start_network()

        await self.start_uart()

        asyncio.create_task(self._uart_to_clients())
        asyncio.create_task(self._monitor_throughput())

        asyncio.create_task(self._display_controller.screensaver_drive())
        asyncio.create_task(self._broadcast_uart_loop())

    async def _identify_flash(self) -> None:
        level = 255
        direction = -20

        while self._identify_active:
            level += direction

            if level <= 0:
                level = 0
                direction = +20

            elif level >= 255:
                level = 255
                direction = -20

            await self._display_controller.set_brightness(level)
            await asyncio.sleep_ms(40)

    async def start_uart(self) -> None:
        uart_conf = self._config.get('picobridge').get('uart')
        physical = uart_conf.get('physical')
        settings = uart_conf.get('settings')

        self._uart: UART = UART(
            physical.get('uart_id'),
            baudrate=settings.get('baudrate'),
            bits=settings.get('bits'),
            parity=settings.get('parity'),
            stop=settings.get('stop'),
            tx=Pin(physical.get('tx_gp')),
            rx=Pin(physical.get('rx_gp')),
            timeout=100,
            timeout_char=20
        )

    async def update_settings(self, new_settings: dict) -> None:
        must_save_config: bool = False
        must_restart: bool = False

        plugged_device = new_settings.get('plugged_device')
        if self._plugged_device != plugged_device:
            self._config['picobridge']['plugged_device'] = plugged_device
            self._plugged_device = plugged_device
            must_save_config = True

        location = new_settings.get('location')
        if self._location != location:
            self._config['picobridge']['location'] = location
            self._location = location
            must_save_config = True

        uart_settings: dict = {
            'baudrate': new_settings.get('baudrate'),
            'bits': new_settings.get('bits'),
            'parity': new_settings.get('parity'),
            'stop': new_settings.get('stop')
        }

        if self._config['picobridge']['uart']['settings'] != uart_settings:
            self._config['picobridge']['uart']['settings'] = uart_settings

            await self.start_uart()

            must_save_config = True

        wlan_settings: dict = new_settings.get('wlan')

        if self._config.get('picobridge').get('wlan') != wlan_settings:
            self._config['picobridge']['wlan'] = wlan_settings

            must_save_config = True
            must_restart = True

        screensaver_enabled = new_settings.get('screensaver').get('screensaver_enabled')
        if self._display_controller.screensaver.is_enabled() != screensaver_enabled:
            self._config['picobridge']['screensaver']['enabled'] = screensaver_enabled
            if screensaver_enabled:
                self._display_controller.screensaver.enable()
                await self._display_controller.show_bar()
            else:
                self._display_controller.screensaver.disable()
                await self._display_controller.hide_bar()

            must_save_config = True

        timeout_s: int = new_settings.get('screensaver').get('screensaver_timeout_s')
        if self._display_controller.screensaver.get_timeout() != timeout_s:
            self._config['picobridge']['screensaver']['timeout_s'] = timeout_s
            self._display_controller.screensaver.set_timeout(timeout_s)
            must_save_config = True

        if must_save_config:
            await self._display_controller.write_to_line(
                line=5,
                text=f"http://{self._ip_address}:{self._web_service_port}, Baud: {new_settings.get('baudrate')}, "
                     f"Device Name: {self._plugged_device}, v{self._version}"
            )
            self.save_config()

        if must_restart:
            sleep_time: int = 5
            self._logger.info(f"PicoBridge Network Settings changed. Restarting in {sleep_time}s")
            await asyncio.sleep(sleep_time)

            reset()

    def get_settings(self) -> dict:
        return {
            'uart': self._config.get('picobridge').get('uart').get('settings').copy(),
            'wlan': self._config.get('picobridge').get('wlan').copy(),
            'screensaver': self._config.get('picobridge').get('screensaver').copy(),
            'plugged_device': self._plugged_device,
            'location': self._location
        }

    def get_version(self) -> str:
        return self._version

    def save_config(self) -> None:
        write_file_as_json(self._config_path, self._config)

    def get_tcp_port(self) -> int:
        return self._tcp_port

    def get_ip_address(self) -> str:
        return self._ip_address

    async def start_network(self) -> None:
        await self._display_controller.disable_scrolling(line=5)

        lines_to_clear = (2, 3, 4, 5)
        for line in lines_to_clear:
            await self._display_controller.clear_line(line=line)

        await asyncio.sleep_ms(100)

        if self._is_ad_hoc:
            wlan_conf = self._config.get('picobridge').get('wlan').get('ad_hoc')
            msg: str = "Starting Network mode: Access Point"
            self._logger.info(msg)

            await self._display_controller.write_to_line(line=2, text=msg[0:16])
            await self._display_controller.write_to_line(line=3, text=msg[23:])
            await asyncio.sleep(3)
            await self._display_controller.clear_line(line=3)

            self._wlan: WLAN = await wlan_ap_mode(ssid=wlan_conf.get('ssid'), password=wlan_conf.get('psk'))
        else:
            try:
                wlan_conf = self._config.get('picobridge').get('wlan').get('infrastructure')
                msg = "Starting Network mode: Infrastructure"
                self._logger.info(msg)

                await self._display_controller.write_to_line(line=2, text=msg[0:16])
                await self._display_controller.write_to_line(line=3, text=msg[23:])

                await asyncio.sleep(3)

                self._wlan = await wlan_infra_mode(
                    ssid=wlan_conf.get('ssid'),
                    password=wlan_conf.get('psk'),
                    display_callback=self._display_controller.write_to_line
                )

            except Exception as e:
                lines_to_clear = (2, 3, 4, 5)
                for line in lines_to_clear:
                    await self._display_controller.clear_line(line)

                self._logger.warning(str(e))

                await self._display_controller.set_scroll_speed(line=5, speed=4)
                await self._display_controller.enable_scrolling(line=5)
                await self._display_controller.write_to_line(line=5, text=str(e))

                await asyncio.sleep(8)
                await self._display_controller.clear_line(line=5)

                self._wlan_restarts += 1

                if self._wlan_restarts > self._wlan_max_restarts:
                    for line in lines_to_clear:
                        await self._display_controller.clear_line(line)

                    while self._reset_timer_due_to_wlan_error > 0:
                        await self._display_controller.write_to_line(line=5, text=f"Resetting in {self._reset_timer_due_to_wlan_error} s...")
                        await asyncio.sleep(1)
                        self._reset_timer_due_to_wlan_error -= 1

                    else:
                        reset()

                await self.start_network()

        self._ip_address = self._wlan.ifconfig()[0]

        baud_rate = self._config.get('picobridge').get('uart').get('settings').get('baudrate')

        await self._display_controller.enable_scrolling(line=5)
        await self._display_controller.set_scroll_speed(line=5, speed=2)
        await self._display_controller.write_to_line(line=5, text=f"http://{self._ip_address}:{self._web_service_port}, Baud: {baud_rate}, Device Name: {self._plugged_device}, v{self._version}")

        await asyncio.sleep(2)

    def wake_uart(self) -> None:
        """Send a wake-up signal (RETURN) to UART to trigger login banner or prompt."""
        try:
            if self._uart:
                self._uart.write(b'\r')

        except Exception as e:
            self._logger.error(f"[Wake UART] {e}")

    async def _uart_to_clients(self, stop_flag: list[bool] = None) -> None:
        if stop_flag is None:
            stop_flag = [False]

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
                    frames = self._terminal_framer.process_chunk(data)
                    if frames:
                        payloads = [json.dumps({"output": f}) for f in frames]
                        await self._ws_manager.broadcast_payloads(payloads)

                    self._led.off()

            # If no new data, check idle flush to push prompts/partials
            if not had_data:
                frames = self._terminal_framer.flush_idle()
                if frames:
                    payloads = [json.dumps({"output": f}) for f in frames]

                    await self._ws_manager.broadcast_payloads(payloads)

                await asyncio.sleep(0.05)

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

    async def _broadcast_uart_loop(self) -> None:
        while True:
            if self._tx_activity or self._rx_activity:
                data = {'tx': self._tx_activity, 'rx': self._rx_activity}

                await self._ws_manager.broadcast_payloads(payloads=[json.dumps(data)])

                self._tx_activity = False
                self._rx_activity = False

            await asyncio.sleep(0.05)

    async def _monitor_throughput(self) -> None:
        await self._display_controller.set_line_alignment(line=3, alignment="left")
        await self._display_controller.set_line_alignment(line=4, alignment="left")

        while True:
            await asyncio.sleep(1)

            now = time.ticks_ms()
            elapsed = time.ticks_diff(now, self._last_stats_time) / 1000
            self._last_stats_time = now

            self._rx_rate = int(self._rx_bytes / elapsed) if elapsed else 0
            self._tx_rate = int(self._tx_bytes / elapsed) if elapsed else 0

            self._rx_bytes = 0
            self._tx_bytes = 0

            await self._ws_manager.broadcast_payloads(
                payloads=[json.dumps({'rx_bps': self._rx_rate, 'tx_bps': self._tx_rate})]
            )

            activity: bool = bool(self._rx_rate or self._tx_rate)

            if activity:
                await self._display_controller.set_last_activity_time(value=now)

            if self._display_controller.screensaver_is_active():
                await self._display_controller.clear_line(line=3)
                await self._display_controller.clear_line(line=4)

            else:
                await self._display_controller.write_to_line(line=3, text=f"RX: {self._rx_rate} b/s")
                await self._display_controller.write_to_line(line=4, text=f"TX: {self._tx_rate} b/s")

    async def _monitor_system(self) -> None:
        while True:
            await asyncio.sleep(1)

            mem_free = self._system_monitor.get_mem_free()
            mem_alloc = self._system_monitor.get_mem_alloc()

            data = {'mem_free': mem_free, 'mem_alloc': mem_alloc}

            await self._ws_manager.broadcast_payloads(payloads=[json.dumps(data)])

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
            self._logger.error(f"[WebSocket Input] {e}")

    def enable_uart_to_crlf(self) -> None:
        self._uart_to_crlf = True

    def disable_uart_to_crlf(self) -> None:
        self._uart_to_crlf = False

    def enable_crlf_to_uart(self) -> None:
        self._crlf_to_uart = True

    def disable_crlf_to_uart(self) -> None:
        self._crlf_to_uart = False

    def display_self_test(self, value: int) -> None:
        self._display_controller.self_test(value=value)

    async def identify_stop(self) -> None:
        self._identify_active = False

        if self._display_controller.screensaver_is_enabled():
            await self._display_controller.activate_screensaver()

        if self._identify_task:
            self._identify_task.cancel()
            self._identify_task = None

        await self._display_controller.reset_brightness()

    async def identify_start(self) -> None:
        if self._identify_active:
            return

        if self._display_controller.screensaver_is_enabled():
            await self._display_controller.deactivate_screensaver()
        self._identify_active = True
        self._identify_task = asyncio.create_task(self._identify_flash())

    async def get_identify(self)-> bool:
        return self._identify_active
