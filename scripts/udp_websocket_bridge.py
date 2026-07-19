"""
udp_websocket_bridge.py - Puente UDP <-> WebSocket (agregador con estado)
Proyecto: AgroDrone - Sistema Inteligente de Control Autonomo para Drones de Riego
Universidad Popular del Cesar

Implementa el bloque "Communication Middleware" descrito en el paper del 20CCC
(Fig. 1 y Fig. 2): recibe telemetria real por UDP desde dos tipos de fuentes
- lecturas de humedad de suelo (sensor_nasa.py)
 - telemetria del dron (mavic_controller.py corriendo en Webots)
las fusiona en un unico snapshot ("Process telemetry" en la Fig. 2) y lo
retransmite por WebSocket a la PWA. Tambien reenvia los comandos de mision
que la PWA envia por WebSocket (start_mission, stop_mission, emergency_stop,
request_status) hacia el controlador del dron por UDP.

Diseno: el bridge NO inventa datos. Todo lo que agrega proviene de paquetes
UDP reales recibidos de sensores o del controlador; unicamente los combina
en una estructura coherente para la PWA (igual que en la Fig. 2 del paper).

Esquema de puertos (evita colisiones con mavic_controller.py):
    5005/UDP  -> el bridge escucha aqui. Sensores de suelo Y el controlador
                 del dron envian su telemetria a este puerto.
    5006/UDP  -> el bridge envia hacia aca: (a) las lecturas de suelo
                 reenviadas "tal cual" para que el controlador las use en su
                 logica difusa, y (b) los comandos de mision de la PWA.
                 mavic_controller.py debe escuchar en este puerto.
    8765/TCP  -> WebSocket hacia la PWA.
"""

import asyncio
import hmac
import json
import socket
import time
import os
import ssl
from pathlib import Path
from urllib.parse import urlparse
from shared_token_credentials import resolve_shared_token
from humidity_thresholds import calculate_humidity_level, interpret_humedad


def encontrar_puerto_libre(inicio: int = 8765, max_intentos: int = 20) -> int:
    for puerto in range(inicio, inicio + max_intentos):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", puerto))
                return puerto
            except OSError:
                continue
    raise RuntimeError("No se encontró un puerto WebSocket libre")
from datetime import datetime
from typing import Set, Optional

import websockets

# ── Configuracion de red ──────────────────────────────────────────────────────
UDP_HOST = "0.0.0.0"
UDP_PORT = 5005          # Entrada: sensores de suelo + telemetria del dron
WS_HOST = "0.0.0.0"
WS_PORT = encontrar_puerto_libre(8765)
CONTROLLER_HOST = "127.0.0.1"
CONTROLLER_CMD_PORT = 5006   # Salida: reenvio de lecturas de suelo + comandos de mision

def _local_address_candidates() -> set[str]:
    candidates = {"localhost", "127.0.0.1"}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            candidates.add(info[4][0])
        fqdn = socket.getfqdn()
        if fqdn:
            candidates.add(fqdn)
    except Exception:
        pass
    return candidates


def _origin_is_allowed(origin: Optional[str]) -> bool:
    if not origin:
        return False
    try:
        parsed = urlparse(origin)
        host = parsed.hostname
        return host in _local_address_candidates()
    except Exception:
        return False


def _get_websocket_headers(websocket) -> dict[str, str]:
    request_headers = getattr(websocket, "request_headers", None)
    if request_headers is not None:
        return request_headers

    request = getattr(websocket, "request", None)
    if request is not None:
        headers = getattr(request, "headers", None)
        if headers is not None:
            return headers

    return {}


def _get_client_ip(websocket) -> str:
    remote_address = getattr(websocket, "remote_address", None)
    if isinstance(remote_address, tuple) and remote_address:
        return str(remote_address[0])
    if isinstance(remote_address, str):
        return remote_address
    return "unknown"


def _cert_sans(cert_path: Path) -> set[str]:
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        cert_bytes = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        return {str(entry.value) for entry in san}
    except ImportError:
        print("[TLS] cryptography no instalado; no se puede leer SAN desde el certificado PEM.")
        return set()
    except Exception:
        return set()


def _find_ssl_cert_pair() -> tuple[Path, Path] | None:
    repo_root = Path(__file__).resolve().parent.parent
    local_addresses = _local_address_candidates()
    candidates: list[tuple[Path, Path, bool]] = []

    for cert_path in sorted(repo_root.glob('*.pem')):
        if cert_path.name.endswith('-key.pem'):
            continue

        key_path = repo_root / f"{cert_path.stem}-key.pem"
        if not key_path.exists():
            continue

        sans = _cert_sans(cert_path)
        matches = bool(local_addresses & sans)
        candidates.append((cert_path, key_path, matches))

    for cert_path, key_path, matches in candidates:
        if matches:
            return cert_path, key_path

    if candidates:
        print("[TLS] Ningún certificado PEM coincide con las direcciones locales; no se seleccionará ningún certificado TLS.")
    return None


SSL_CONTEXT: ssl.SSLContext | None = None
cert_pair = _find_ssl_cert_pair()
if cert_pair is not None:
    CERT_FILE, KEY_FILE = cert_pair
    try:
        SSL_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        SSL_CONTEXT.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
        print(f"[TLS] Usando certificados: {CERT_FILE} / {KEY_FILE}")
    except Exception as exc:
        print(f"[TLS] No se pudo cargar el contexto TLS: {exc}")
        SSL_CONTEXT = None
else:
    print("[TLS] No se encontró ningún par de certificados TLS válido; el bridge funcionará en ws://")

ZONE_NAMES = ("norte", "centro", "sur")

resolve_shared_token()
SHARED_TOKEN = (
    os.environ.get("AGRODRONE_SHARED_TOKEN")
    or os.environ.get("VITE_SHARED_TOKEN")
    or ""
)

if not SHARED_TOKEN:
    print("[SEGURIDAD] No hay token compartido configurado; ejecuta set_shared_token.py "
          "para habilitar la autenticación entre bridge, sensores y controlador.")
else:
    print(f"[SEGURIDAD] Token compartido cargado: {SHARED_TOKEN[:4]}***")


def token_es_valido(token_recibido: Optional[str]) -> bool:
    """Acepta el token compartido cuando está presente y coincide con el valor cargado."""
    if not SHARED_TOKEN:
        return True

    if not isinstance(token_recibido, str):
        return False

    token_recibido = token_recibido.strip()
    if token_recibido == "":
        return False

    if hmac.compare_digest(token_recibido, SHARED_TOKEN):
        return True

    print("[TOKEN] Token recibido no coincide con el valor esperado")
    return False

# ── Estado agregado (fusion de todas las fuentes UDP recibidas) ──────────────
zone_readings = {
    "norte": {"humedad": 75.0, "estado": "humedo", "temperatura": 30.0},
    "centro": {"humedad": 50.0, "estado": "normal", "temperatura": 32.0},
    "sur": {"humedad": 25.0, "estado": "seco", "temperatura": 35.0},
}
last_reading: Optional[dict] = None
reading_history: list = []

drone_state = {
    "flightStatus": "idle",
    "battery": 100.0,
    "position": {"x": 50.0, "y": 80.0, "z": 0.0},
    "targetZone": None,
    "waterLevel": 100.0,
    "speed": 0.0,
    "altitude": 0.0,
    "modo": "auto",
    "missionProgress": 0.0,
}
target_position = {"x": 50.0, "y": 80.0, "z": 0.0}
last_drone_packet_ts: Optional[float] = None

# Efecto real de riego: mientras el dron esta REGANDO una zona, su humedad
# sube (esto es lo que hace que la mision tenga sentido - sin esto, regar
# no cambiaba nada y la zona volvia a activar otra mision de inmediato).
# Se modela como un "boost" que se SUMA a la lectura cruda del sensor antes
# de fusionarla, y se aplica tanto a lo que ve la PWA como a lo que se
# reenvia al controlador (asi la logica difusa del controlador ve el mismo
# valor "verdadero" que la PWA, no uno crudo y otro corregido).
IRRIGATION_INCREMENT = 5.0   # % de humedad que sube por cada tick de riego (~1 Hz)
IRRIGATION_DECAY = 0.3       # % que se evapora por tick cuando no se riega
irrigation_boost = {"norte": 0.0, "centro": 0.0, "sur": 0.0}

connected_clients: Set = set()

# Socket UDP de salida hacia el controlador (comandos + reenvio de suelo)
controller_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
controller_sock.setblocking(False)



def calcular_zonas_humedad() -> dict:
    zones = {"lv0": 0, "lv1": 0, "lv2": 0, "lv3": 0, "lv4": 0, "lv5": 0}
    for data in zone_readings.values():
        zones[calculate_humidity_level(data["humedad"])] += 1
    return zones


def estimar_signal() -> float:
    """Heuristica honesta de calidad de enlace: basada en cuanto hace que
    llego el ultimo paquete de telemetria del dron, no un valor inventado."""
    if last_drone_packet_ts is None:
        return 0.0
    elapsed = time.monotonic() - last_drone_packet_ts
    if elapsed <= 1.5:
        return 100.0
    if elapsed >= 6.0:
        return 0.0
    return max(0.0, 100.0 * (1 - (elapsed - 1.5) / 4.5))


def build_snapshot() -> dict:
    avg_humidity = sum(z["humedad"] for z in zone_readings.values()) / len(zone_readings)
    target_zone = drone_state.get("targetZone")
    ambient_temp_zone = target_zone if target_zone in zone_readings else "centro"
    return {
        "type": "telemetry_update",
        "timestamp": datetime.now().isoformat(),
        "zones": {
            name: {
                "humedad": data["humedad"],
                "estado": data["estado"],
                "temperatura": data["temperatura"],
                "nivel": calculate_humidity_level(data["humedad"]),
            }
            for name, data in zone_readings.items()
        },
        "humidityZones": calcular_zonas_humedad(),
        "averageHumidity": avg_humidity,
        "drone": dict(drone_state),
        "coordinates": drone_state["position"],
        "targetPosition": target_position,
        "signal": estimar_signal(),
        "temperature": zone_readings[ambient_temp_zone]["temperatura"],
        "speed": drone_state.get("speed", 0.0),
        "lastReading": last_reading,
        "history": reading_history[-10:],
    }


async def broadcast_snapshot():
    if not connected_clients:
        return
    message = json.dumps(build_snapshot())
    await asyncio.gather(
        *[client.send(message) for client in connected_clients],
        return_exceptions=True,
    )

VALID_ZONES = frozenset(zone_readings.keys())

def procesar_lectura_suelo(datos: dict):
    global last_reading

    zona_recibida = datos.get("zona", "centro")
    if zona_recibida not in VALID_ZONES:
        print(f"[UDP] Zona desconocida '{zona_recibida}' en paquete de suelo; "
              f"descartando paquete (no se usa fallback silencioso a 'centro').")
        return
    zona = zona_recibida

    try:
        humedad_cruda = float(datos["humedad"])
    except (TypeError, ValueError):
        print(f"[UDP] Lectura de suelo descartada: humedad inválida {datos.get('humedad')!r} "
            f"para zona {datos.get('zona')!r}")
        return
    boost = irrigation_boost.get(zona, 0.0)
    humedad = min(100.0, humedad_cruda + boost)
    # La etiqueta la recalculamos aqui (no la que trae el paquete) porque
    # puede quedar desactualizada despues de sumar el boost de riego.
    estado = interpret_humedad(humedad)
    temperatura = float(datos.get("temperatura", zone_readings[zona]["temperatura"]))

    zone_readings[zona] = {"humedad": humedad, "estado": estado, "temperatura": temperatura}

    entry = {
        "zona": zona,
        "humedad": humedad,
        "estado": estado,
        "temperatura": temperatura,
        # Preferir el timestamp generado por el propio sensor (paper, seccion 2.2:
        # "each telemetry packet includes... timestamp"). Solo se usa la hora del
        # bridge como respaldo si un sensor viejo no lo envia.
        "timestamp": datos.get("timestamp") or datetime.now().isoformat(),
    }
    # Passthrough de campos de instrumentacion (usados por measure_bridge_latency.py)
    if datos.get("probe_id") is not None:
        entry["probe_id"] = datos["probe_id"]
    if datos.get("send_ts") is not None:
        entry["send_ts"] = datos["send_ts"]

    last_reading = entry
    reading_history.append(entry)
    if len(reading_history) > 100:
        reading_history.pop(0)

    # Reenviar al controlador la lectura YA CORREGIDA (con el boost de riego
    # aplicado), no la cruda — asi la logica difusa del controlador ve el
    # mismo valor "verdadero" que la PWA, y detecta correctamente cuando una
    # zona que se estaba regando ya no lo necesita.
    paquete_corregido = {**datos, "humedad": humedad, "estado_suelo": estado}
    try:
        controller_sock.sendto(json.dumps(paquete_corregido).encode("utf-8"), (CONTROLLER_HOST, CONTROLLER_CMD_PORT))
    except Exception as exc:
        print(f"[CTRL] No se pudo reenviar lectura de suelo: {exc}")

def _safe_float(datos: dict, key: str, current_value: float) -> float:
    """Devuelve el nuevo valor si es convertible, o el valor actual si no."""
    if key not in datos:
        return current_value
    try:
        return float(datos[key])
    except (TypeError, ValueError):
        print(f"[UDP] Campo '{key}' inválido en telemetría del dron: {datos[key]!r}; "
              f"se conserva el valor anterior ({current_value}).")
        return current_value

def procesar_telemetria_dron(datos: dict):
    global last_drone_packet_ts

    drone_state["flightStatus"] = datos.get("flightStatus", drone_state["flightStatus"])
    drone_state["battery"] = _safe_float(datos, "battery", drone_state["battery"])
    drone_state["waterLevel"] = _safe_float(datos, "waterLevel", drone_state["waterLevel"])
    drone_state["speed"] = _safe_float(datos, "speed", drone_state["speed"])
    drone_state["altitude"] = _safe_float(datos, "altitude", drone_state["altitude"])
    drone_state["missionProgress"] = _safe_float(datos, "missionProgress", drone_state["missionProgress"])
    if "modo" in datos:
        drone_state["modo"] = datos["modo"]
    if "targetZone" in datos:
        drone_state["targetZone"] = datos["targetZone"]
    if isinstance(datos.get("position"), dict):
        drone_state["position"] = {
            "x": float(datos["position"].get("x", drone_state["position"]["x"])),
            "y": float(datos["position"].get("y", drone_state["position"]["y"])),
            "z": float(datos["position"].get("z", drone_state["position"]["z"])),
        }
    if isinstance(datos.get("targetPosition"), dict):
        target_position["x"] = float(datos["targetPosition"].get("x", target_position["x"]))
        target_position["y"] = float(datos["targetPosition"].get("y", target_position["y"]))
        target_position["z"] = float(datos["targetPosition"].get("z", target_position.get("z", 0.0)))

    # Efecto real de riego: mientras el dron esta "regando" la zona objetivo,
    # su humedad sube en cada tick de telemetria (~1 Hz, ver
    # TELEMETRY_INTERVAL_S en mavic_controller.py). El resto de zonas (y
    # esta misma cuando no se riega) se evaporan lentamente. El boost se
    # aplica a la proxima lectura cruda que llegue en procesar_lectura_suelo,
    # que sigue siendo la fuente de verdad de cada zona.
    target_zone = drone_state.get("targetZone")
    for zona in irrigation_boost:
        if drone_state["flightStatus"] == "regando" and zona == target_zone:
            irrigation_boost[zona] = min(60.0, irrigation_boost[zona] + IRRIGATION_INCREMENT)
        else:
            irrigation_boost[zona] = max(0.0, irrigation_boost[zona] - IRRIGATION_DECAY)

    last_drone_packet_ts = time.monotonic()


async def udp_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.setblocking(False)

    loop = asyncio.get_event_loop()
    print(f"[UDP] Escuchando en {UDP_HOST}:{UDP_PORT}")

    while True:
        try:
            data, addr = await loop.sock_recvfrom(sock, 65536)
            try:
                datos = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                print(f"[UDP] Paquete no-JSON descartado de {addr}")
                continue

            if not token_es_valido(datos.get("token")):
                print(f"[UDP] Paquete con token inválido o ausente descartado de {addr}")
                continue

            if datos.get("type") == "drone_telemetry":
                procesar_telemetria_dron(datos)
            elif "zona" in datos and "humedad" in datos:
                procesar_lectura_suelo(datos)
            else:
                print(f"[UDP] Paquete de forma desconocida ignorado: {datos}")
                continue

            await broadcast_snapshot()

        except BlockingIOError:
            await asyncio.sleep(0.01)
        except Exception as e:
            print(f"[UDP] Error en receiver: {e}")
            await asyncio.sleep(0.1)

async def websocket_handler(websocket):
    headers = _get_websocket_headers(websocket)
    origin = headers.get('Origin') or headers.get('origin')
    if not _origin_is_allowed(origin):
        client_ip = _get_client_ip(websocket)
        print(f"[WS] Origen no permitido {origin!r} desde {client_ip}; cerrando conexion")
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    client_ip = _get_client_ip(websocket)
    if SHARED_TOKEN:
        try:
            first_message = await asyncio.wait_for(websocket.recv(), timeout=5)
        except asyncio.TimeoutError:
            print(f"[WS] Timeout de autenticación desde {client_ip}; cerrando conexion")
            await websocket.close(code=1008, reason="Authentication required")
            return
        except websockets.exceptions.ConnectionClosed:
            print(f"[WS] Conexion cerrada antes de autenticar desde {client_ip}")
            return

        try:
            auth_payload = json.loads(first_message)
        except json.JSONDecodeError:
            print(f"[WS] Primer mensaje no es JSON válido desde {client_ip}; cerrando conexion")
            await websocket.close(code=1008, reason="Authentication required")
            return

        if auth_payload.get("type") != "auth" or not token_es_valido(auth_payload.get("token")):
            print(f"[WS] Autenticación fallida desde {client_ip}; cerrando conexion")
            await websocket.close(code=1008, reason="Authentication required")
            return

    connected_clients.add(websocket)
    print(f"[WS] Nueva conexion desde {client_ip}")

    try:
        await websocket.send(json.dumps({**build_snapshot(), "type": "initial_state"}))

        async for message in websocket:
            try:
                cmd = json.loads(message)
            except json.JSONDecodeError:
                print(f"[WS] Comando invalido: {message}")
                continue

            if not token_es_valido(cmd.get("token")):
                print(f"[WS] Comando con token inválido o ausente descartado de {client_ip}")
                continue

            cmd_type = cmd.get("type")

            if cmd_type == "request_status":
                reply = build_snapshot()
                # Eco del timestamp del cliente (medido con SU propio reloj de
                # navegador) para que la PWA calcule latencia real ida-y-vuelta
                # sin depender de que los relojes de dos maquinas esten sincronizados.
                if cmd.get("client_ts") is not None:
                    reply["pingTs"] = cmd["client_ts"]
                await websocket.send(json.dumps(reply))
                continue

            if cmd_type in ("start_mission", "stop_mission", "emergency_stop", "set_mode"):
                try:
                    forward = {**cmd, "token": SHARED_TOKEN}
                    controller_sock.sendto(json.dumps(forward).encode("utf-8"), (CONTROLLER_HOST, CONTROLLER_CMD_PORT))
                    print(f"[CMD] Reenviado a controlador: {cmd}")
                except Exception as e:
                    print(f"[CMD] Error reenviando comando: {e}")
            else:
                print(f"[WS] Comando desconocido ignorado: {cmd}")

    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] Conexion cerrada: {client_ip}")
    finally:
        connected_clients.discard(websocket)


async def main():
    print("=" * 60)
    print("  PUENTE UDP-WEBSOCKET - AGREGADOR DE TELEMETRIA")
    print("  Universidad Popular del Cesar")
    print("=" * 60)
    print(f"  UDP entrada:              {UDP_HOST}:{UDP_PORT}")
    print(f"  UDP salida (controlador): {CONTROLLER_HOST}:{CONTROLLER_CMD_PORT}")
    print(f"  WebSocket:                {'wss' if SSL_CONTEXT else 'ws'}://{WS_HOST}:{WS_PORT}")
    print(f"  Puerto WebSocket activo:  {WS_PORT}")
    print()

    ws_server = await websockets.serve(
        websocket_handler,
        WS_HOST,
        WS_PORT,
        ssl=SSL_CONTEXT,
    )
    udp_task = asyncio.create_task(udp_receiver())

    await asyncio.gather(ws_server.wait_closed(), udp_task, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SISTEMA] Apagando servidor...")
