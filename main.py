import asyncio

from libraries.microdot.microdot import Microdot, Response, send_file
from libraries.microdot.utemplate import Template
from libraries.microdot.websocket import with_websocket

from src.file_handlers import read_file_as_json
from src.logger import Logger
from src.picobridge import PicoBridge
from src.telnet import TELNET_INIT

config_file: str = 'config.json'
config: dict = read_file_as_json(filename=config_file)

app: Microdot = Microdot()

Response.default_content_type = 'text/html'
STATIC_FOLDER: str = "static/"

logging: Logger = Logger("PicoBridge")

pico_bridge: PicoBridge = PicoBridge()


async def handle_client(reader, writer) -> None:
    stop_flag = [False]
    pico_bridge.clients.append(writer)

    try:
        peer_ip, _ = writer.get_extra_info('peername')
        logging.info(f"Client connected from {peer_ip}")

    except:
        logging.info("Client connected (IP unknown)")

    try:
        writer.write(TELNET_INIT)
        await writer.drain()

    except:
        pass

    pico_bridge.wake_uart()

    try:
        await asyncio.gather(pico_bridge.client_to_uart(reader, writer, stop_flag))

    finally:
        if writer in pico_bridge.clients:
            pico_bridge.clients.remove(writer)

        try:
            writer.close()

        except:
            pass

        logging.info("Client disconnected")


@app.get('/static/<path:path>')
async def static(req, path):
    if '..' in path:
        # directory traversal is not allowed
        return 'Not found', 404

    return send_file(STATIC_FOLDER + path)

@app.get('/')
async def index(req):
    return Template(template='index.html').render(version=pico_bridge.get_version())


@app.route('/ws')
@with_websocket
async def ws_handler(request, ws):
    ip, _ = request.client_addr
    logging.info(f"WebSocket client connected from {ip}")

    pico_bridge.register_websocket(ws)

    try:
        while True:
            data = await ws.receive()
            await pico_bridge.handle_websocket_input(data)

    except:
        pass

    finally:
        pico_bridge.unregister_websocket(ws)
        logging.info("WebSocket client disconnected")


@app.route('/echo')
@with_websocket
async def echo(request, ws):
    while True:
        data = await ws.receive()
        await ws.send(data)


@app.get('/api/v1/pb/settings')
async def get_pb_settings(req):
    settings: dict = pico_bridge.get_settings()
    return settings


@app.post('/api/v1/pb/settings')
async def update_settings(req):
    new_settings: dict = req.json
    await pico_bridge.update_settings(new_settings=new_settings)

    return {'message': 'UART settings updated'}


@app.get('api/v1/pb/uart_to_crlf/enable')
async def uart_to_crlf_enable(req):
    pico_bridge.enable_uart_to_crlf()


@app.get('api/v1/pb/uart_to_crlf/disable')
async def uart_to_crlf_disable(req):
    pico_bridge.disable_uart_to_crlf()


@app.get('api/v1/pb/crlf_to_uart/enable')
async def crlf_to_uart_enable(req):
    pico_bridge.enable_crlf_to_uart()


@app.get('api/v1/pb/crlf_to_uart/disable')
async def crlf_to_uart_disable(req):
    pico_bridge.disable_crlf_to_uart()


async def start_microdot(ip: str) -> None:
    await app.start_server(host=ip, port=config.get('picobridge').get('webservice').get('port'), debug=True)


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

    logging.info(f"Listening on {ip}: {tcp_port}")

    try:
        await asyncio.gather(start_microdot(ip=ip))

    finally:
        srv.close()

        try:
            await srv.wait_closed()

        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())
