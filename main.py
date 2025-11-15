import asyncio

from libraries.microdot.microdot import Microdot, Response, send_file
from libraries.microdot.utemplate import Template
from libraries.microdot.websocket import with_websocket

from src.file_handlers import read_file_as_json
from src.logger import Logger
from src.websocket_manager import WebsocketManager
from src.picobridge import PicoBridge
from src.telnet import TELNET_INIT

config_file: str = 'config.json'
config: dict = read_file_as_json(filename=config_file)

app: Microdot = Microdot()

Response.default_content_type = 'text/html'
STATIC_FOLDER: str = "static/"

logger: Logger = Logger("PicoBridge")

websocket_manager: WebsocketManager = WebsocketManager(logger=logger)

pico_bridge: PicoBridge = PicoBridge()


async def handle_client(reader, writer) -> None:
    stop_flag = [False]
    pico_bridge.clients.append(writer)

    try:
        peer = writer.get_extra_info('peername')
        if peer:
            peer_ip, _ = peer
            logger.info(f"Client connected from {peer_ip}")
        else:
            logger.info("Client connected (peername not available)")

    except Exception as e:
        logger.info(f"Client connected (IP unknown): {e}")

    try:
        writer.write(TELNET_INIT)
        await writer.drain()

    except Exception as e:
        logger.info(f"Error sending TELNET_INIT: {e}")

    pico_bridge.wake_uart()

    try:
        await asyncio.gather(pico_bridge.client_to_uart(reader, writer, stop_flag))

    finally:
        if writer in pico_bridge.clients:
            pico_bridge.clients.remove(writer)

        try:
            writer.close()
            try:
                await writer.wait_closed()

            except Exception:
                pass

        except Exception as e:
            logger.info(f"Error closing writer: {e}")

        logger.info("Client disconnected")


@app.get('/static/<path:path>')
async def static(req, path):
    if '..' in path:
        return 'Not found', 404

    return send_file(STATIC_FOLDER + path)

@app.get('/')
async def index(req):
    return Template(template='index.html').render(version=pico_bridge.get_version())


@app.route('/ws')
@with_websocket
async def ws_handler(request, ws):
    try:
        ip, _ = request.client_addr

    except Exception:
        ip = 'unknown'
    
    logger.info(f"WebSocket client connected from {ip}")

    pico_bridge.register_websocket(ws)

    try:
        while True:
            try:
                data = await ws.receive()
            except Exception as e:
                logger.info(f"WebSocket receive error: {e}")
                break

            if data is None:
                break

            try:
                await pico_bridge.handle_websocket_input(data)
            except Exception as e:
                logger.info(f"Error handling websocket input: {e}")
                # continue loop; do not crash the websocket handler
                continue
    
    except Exception as e:
        logger.info(f"Unexpected websocket handler error: {e}")

    finally:
        pico_bridge.unregister_websocket(ws)
        logger.info("WebSocket client disconnected")


@app.get('/api/v1/pb/settings')
async def get_pb_settings(req):
    settings: dict = pico_bridge.get_settings()
    return settings


@app.post('/api/v1/pb/settings')
async def update_settings(req):
    new_settings: dict = req.json
    await pico_bridge.update_settings(new_settings=new_settings)

    return {'message': 'Settings updated'}


@app.get('/api/v1/pb/uart_to_crlf/enable')
async def uart_to_crlf_enable(req):
    pico_bridge.enable_uart_to_crlf()
    return {'message': 'uart_to_crlf enabled'}


@app.get('/api/v1/pb/uart_to_crlf/disable')
async def uart_to_crlf_disable(req):
    pico_bridge.disable_uart_to_crlf()
    return {'message': 'uart_to_crlf disabled'}


@app.get('/api/v1/pb/crlf_to_uart/enable')
async def crlf_to_uart_enable(req):
    pico_bridge.enable_crlf_to_uart()
    return {'message': 'crlf_to_uart enabled'}


@app.get('/api/v1/pb/crlf_to_uart/disable')
async def crlf_to_uart_disable(req):
    pico_bridge.disable_crlf_to_uart()
    return {'message': 'crlf_to_uart disabled'}


async def start_microdot(ip: str) -> None:
    port = config.get('picobridge', {}).get('webservice', {}).get('port', 8080)

    try:
        await app.start_server(host=ip, port=port, debug=True)

    except Exception as e:
        logger.info(f"Error starting microdot server on {ip}:{port} - {e}")
        raise


async def main() -> None:
    pico_bridge.start_network()
    ip: str = pico_bridge.get_ip_address()
    tcp_port: int = pico_bridge.get_tcp_port()
    stop_flag: list[bool] = [False]

    pico_bridge.start_uart()
    # Start UART <-> client bridge
    asyncio.create_task(pico_bridge.uart_to_clients(stop_flag))
    asyncio.create_task(pico_bridge.monitor_throughput())
    asyncio.create_task(pico_bridge.monitor_system())

    # Start WebSocket broadcast for UI indicators
    asyncio.create_task(pico_bridge.broadcast_uart_loop())

    srv = await asyncio.start_server(handle_client, ip, tcp_port)

    logger.info(f"Listening on {ip}: {tcp_port}")

    try:
        await asyncio.gather(start_microdot(ip=ip))

    finally:
        srv.close()

        try:
            await srv.wait_closed()

        except Exception as e:
            logger.info(f"Error waiting for server close: {e}")


if __name__ == "__main__":
    asyncio.run(main())
