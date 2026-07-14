"""
udp_websocket_bridge.py - Puente UDP a WebSocket (forwarder)
Recibe paquetes UDP (sensores o Webots) y los reenvía tal cual a la PWA via WebSocket.
También reenvía comandos recibidos por WebSocket hacia Webots por UDP.

Diseño: no se fabrican ni simulan datos en este puente. Todo se reenvía "real".
"""

import asyncio
import json
import socket
import websockets
from typing import Set, Optional

# ── Configuración de red ──────────────────────────────────────────────────────
UDP_HOST = "0.0.0.0"
UDP_PORT = 5005
WS_HOST = "0.0.0.0"
WS_PORT = 8765
WEBOTS_HOST = "127.0.0.1"
WEBOTS_PORT = 5006

# Conjuntos y estado simples
connected_clients: Set[websockets.WebSocketServerProtocol] = set()
last_raw_packet: Optional[str] = None

# Socket UDP global para reenviar comandos/paquetes a Webots
webots_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
webots_sock.setblocking(False)


async def udp_receiver():
    """Recibe paquetes UDP y los reenvía a Webots y a los clientes WebSocket.
    Este loop no transforma el contenido; solo lo reenvía.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.setblocking(False)

    loop = asyncio.get_event_loop()
    print(f"[UDP] Escuchando en {UDP_HOST}:{UDP_PORT}")

    while True:
        try:
            data, addr = await loop.sock_recvfrom(sock, 65536)
            try:
                mensaje = data.decode('utf-8')
            except Exception:
                # Binary payload: forward as-is to Webots and skip WS (WS expects text)
                webots_sock.sendto(data, (WEBOTS_HOST, WEBOTS_PORT))
                print(f"[UDP] Reenviado paquete binario a Webots desde {addr}")
                continue

            # Log parsed JSON when possible
            try:
                parsed = json.loads(mensaje)
                print(f"[UDP] Recibido de {addr}: {parsed}")
            except Exception:
                print(f"[UDP] Recibido de {addr}: (texto no-JSON)")

            # Reenviar exactamente el mismo paquete a Webots (para que el controlador lo reciba)
            webots_sock.sendto(data, (WEBOTS_HOST, WEBOTS_PORT))

            # Guardar último paquete para clientes que se conecten después
            global last_raw_packet
            last_raw_packet = mensaje

            # Reenviar a todos los clientes WebSocket conectados
            if connected_clients:
                await asyncio.gather(
                    *[client.send(mensaje) for client in connected_clients],
                    return_exceptions=True,
                )
                print(f"[WS] Enviado a {len(connected_clients)} cliente(s)")

        except BlockingIOError:
            await asyncio.sleep(0.01)
        except Exception as e:
            print(f"[UDP] Error en receiver: {e}")
            await asyncio.sleep(0.1)


async def websocket_handler(websocket: websockets.WebSocketServerProtocol):
    """Maneja conexiones WebSocket de la PWA.
    - Envía el último paquete recibido (si existe) como estado inicial.
    - Reenvía los mensajes entrantes del cliente hacia Webots por UDP.
    """
    connected_clients.add(websocket)
    client_ip = websocket.remote_address[0] if websocket.remote_address else 'unknown'
    print(f"[WS] Nueva conexión desde {client_ip}")

    try:
        # Enviar estado inicial tal cual (si existe)
        if last_raw_packet:
            try:
                await websocket.send(last_raw_packet)
            except Exception:
                await websocket.send(json.dumps({"type": "initial_state", "message": "no data"}))
        else:
            await websocket.send(json.dumps({"type": "initial_state", "message": "no data"}))

        async for message in websocket:
            # Esperamos que la PWA envíe comandos JSON; los reenviamos por UDP a Webots
            try:
                cmd = json.loads(message)
            except Exception:
                print(f"[WS] Mensaje no-JSON recibido desde PWA: {message}")
                continue

            try:
                payload = json.dumps(cmd).encode('utf-8')
                webots_sock.sendto(payload, (WEBOTS_HOST, WEBOTS_PORT))
                print(f"[CMD] Reenviado a Webots: {cmd}")
            except Exception as e:
                print(f"[CMD] Error reenviando a Webots: {e}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] Conexion cerrada: {client_ip}")
    finally:
        connected_clients.discard(websocket)


async def main():
    print("=" * 60)
    print("  PUENTE UDP-WEBSOCKET - FORWARDER")
    print("=" * 60)
    print(f"  UDP:       {UDP_HOST}:{UDP_PORT}")
    print(f"  WebSocket: ws://{WS_HOST}:{WS_PORT}")
    print()

    ws_server = await websockets.serve(websocket_handler, WS_HOST, WS_PORT)
    udp_task = asyncio.create_task(udp_receiver())

    await asyncio.gather(ws_server.wait_closed(), udp_task, return_exceptions=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n[SISTEMA] Apagando servidor...')
