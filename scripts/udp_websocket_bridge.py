"""
udp_websocket_bridge.py - Puente UDP a WebSocket para la PWA
Proyecto: Sistema Inteligente de Control Autonomo para Drones de Riego
Universidad Popular del Cesar

Este script:
1. Recibe datos UDP del sensor_mock.py o sensor_nasa.py (puerto 5005)
2. Los reenvía via WebSocket a la PWA (puerto 8765)
3. Mantiene un historial de lecturas por zona

Uso:
    python udp_websocket_bridge.py

La PWA debe conectarse a ws://localhost:8765 para recibir los datos.
"""

import asyncio
import json
import socket
import websockets
from datetime import datetime
from typing import Set
from dataclasses import dataclass, asdict

# ── Configuración de red ──────────────────────────────────────────────────────
UDP_HOST = "0.0.0.0"
UDP_PORT = 5005          # Puerto donde llegan los datos del sensor
WS_HOST  = "localhost"
WS_PORT  = 8765          # Puerto WebSocket para la PWA

# ── Estado global del sistema ─────────────────────────────────────────────────
connected_clients: Set[websockets.WebSocketServerProtocol] = set()

@dataclass
class ZoneReading:
    """Lectura de una zona especifica"""
    zona: str
    humedad: float
    estado_suelo: str
    temperatura: float
    timestamp: str
    
@dataclass 
class DroneState:
    """Estado actual del dron"""
    flight_status: str = "idle"  # idle, ascenso, navegando, regando, retorno, descenso
    battery: int = 100
    position: dict = None
    target_zone: str = None
    water_level: int = 100
    
    def __post_init__(self):
        if self.position is None:
            self.position = {"x": 0.0, "y": 0.0, "z": 0.0}

# Estado actual
zone_readings = {
    "norte":  {"humedad": 75, "estado": "humedo", "temperatura": 30.0},
    "centro": {"humedad": 50, "estado": "normal", "temperatura": 32.0},
    "sur":    {"humedad": 25, "estado": "seco",   "temperatura": 35.0},
}
reading_history = []
drone_state = DroneState()

# ── Funciones de procesamiento ────────────────────────────────────────────────

def calcular_nivel_humedad(humedad: float) -> str:
    """Calcula el nivel lv0-lv5 basado en humedad"""
    if humedad < 25:
        return "lv0"  # Critico
    elif humedad < 40:
        return "lv1"  # Bajo
    elif humedad < 55:
        return "lv2"  # Moderado
    elif humedad < 70:
        return "lv3"  # Optimo
    elif humedad < 85:
        return "lv4"  # Alto
    else:
        return "lv5"  # Saturado

def calcular_zonas_humedad() -> dict:
    """Calcula conteo de zonas por nivel de humedad"""
    zones = {"lv0": 0, "lv1": 0, "lv2": 0, "lv3": 0, "lv4": 0, "lv5": 0}
    for zona, data in zone_readings.items():
        nivel = calcular_nivel_humedad(data["humedad"])
        zones[nivel] += 1
    return zones

def procesar_datos_sensor(datos: dict) -> dict:
    """Procesa datos entrantes del sensor y actualiza estado"""
    global zone_readings, drone_state
    
    zona = datos.get("zona", "centro")
    humedad = float(datos.get("humedad", 50))
    estado = datos.get("estado_suelo", "normal")
    temperatura = float(datos.get("temperatura", 30.0))
    
    # Actualizar lecturas de zona
    zone_readings[zona] = {
        "humedad": humedad,
        "estado": estado,
        "temperatura": temperatura,
    }
    
    # Agregar al historial
    reading_history.append({
        "zona": zona,
        "humedad": humedad,
        "estado": estado,
        "temperatura": temperatura,
        "timestamp": datetime.now().isoformat(),
    })
    
    # Mantener solo las ultimas 100 lecturas
    if len(reading_history) > 100:
        reading_history.pop(0)
    
    # Calcular promedio general
    avg_humidity = sum(z["humedad"] for z in zone_readings.values()) / len(zone_readings)
    
    # Simular estado del dron basado en humedad
    if estado == "muy_seco" and drone_state.flight_status == "idle":
        drone_state.flight_status = "ascenso"
        drone_state.target_zone = zona
    elif drone_state.flight_status == "regando" and estado in ["normal", "humedo"]:
        drone_state.flight_status = "retorno"
    
    # Construir paquete de telemetria para la PWA
    return {
        "type": "telemetry_update",
        "timestamp": datetime.now().isoformat(),
        "zones": {
            zona_name: {
                "humedad": zone_data["humedad"],
                "estado": zone_data["estado"],
                "temperatura": zone_data["temperatura"],
                "nivel": calcular_nivel_humedad(zone_data["humedad"]),
            }
            for zona_name, zone_data in zone_readings.items()
        },
        "humidityZones": calcular_zonas_humedad(),
        "averageHumidity": avg_humidity,
        "drone": {
            "flightStatus": drone_state.flight_status,
            "battery": drone_state.battery,
            "position": drone_state.position,
            "targetZone": drone_state.target_zone,
            "waterLevel": drone_state.water_level,
        },
        "lastReading": {
            "zona": zona,
            "humedad": humedad,
            "estado": estado,
            "temperatura": temperatura,
        },
        "history": reading_history[-10:],  # Ultimas 10 lecturas
    }

# ── Servidor UDP ──────────────────────────────────────────────────────────────

async def udp_receiver():
    """Recibe datos UDP del sensor y los reenvía a clientes WebSocket"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.setblocking(False)
    
    print(f"[UDP] Escuchando en {UDP_HOST}:{UDP_PORT}")
    
    loop = asyncio.get_event_loop()
    
    while True:
        try:
            data, addr = await loop.sock_recvfrom(sock, 4096)
            mensaje = data.decode("utf-8")
            datos = json.loads(mensaje)
            
            print(f"[UDP] Recibido de {addr}: {datos}")
            
            # Procesar y crear paquete de telemetria
            telemetry_packet = procesar_datos_sensor(datos)
            
            # Enviar a todos los clientes WebSocket conectados
            if connected_clients:
                websockets_message = json.dumps(telemetry_packet)
                await asyncio.gather(
                    *[client.send(websockets_message) for client in connected_clients],
                    return_exceptions=True
                )
                print(f"[WS] Enviado a {len(connected_clients)} cliente(s)")
                
        except BlockingIOError:
            await asyncio.sleep(0.01)
        except json.JSONDecodeError as e:
            print(f"[UDP] Error parseando JSON: {e}")
        except Exception as e:
            print(f"[UDP] Error: {e}")
            await asyncio.sleep(0.1)

# ── Servidor WebSocket ────────────────────────────────────────────────────────

async def websocket_handler(websocket: websockets.WebSocketServerProtocol):
    """Maneja conexiones WebSocket de la PWA"""
    connected_clients.add(websocket)
    client_ip = websocket.remote_address[0]
    print(f"[WS] Nueva conexion desde {client_ip}")
    
    try:
        # Enviar estado inicial
        initial_state = {
            "type": "initial_state",
            "zones": zone_readings,
            "humidityZones": calcular_zonas_humedad(),
            "averageHumidity": sum(z["humedad"] for z in zone_readings.values()) / len(zone_readings),
            "drone": asdict(drone_state),
            "history": reading_history[-10:],
        }
        await websocket.send(json.dumps(initial_state))
        
        # Escuchar comandos de la PWA
        async for message in websocket:
            try:
                command = json.loads(message)
                await handle_pwa_command(websocket, command)
            except json.JSONDecodeError:
                print(f"[WS] Comando invalido: {message}")
                
    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] Conexion cerrada: {client_ip}")
    finally:
        connected_clients.discard(websocket)

async def handle_pwa_command(websocket, command: dict):
    """Procesa comandos enviados desde la PWA"""
    global drone_state
    
    cmd_type = command.get("type")
    
    if cmd_type == "start_mission":
        drone_state.flight_status = "ascenso"
        drone_state.target_zone = command.get("target_zone", "sur")
        print(f"[CMD] Iniciando mision hacia zona {drone_state.target_zone}")
        
    elif cmd_type == "stop_mission":
        drone_state.flight_status = "retorno"
        print("[CMD] Deteniendo mision, regresando a base")
        
    elif cmd_type == "emergency_stop":
        drone_state.flight_status = "descenso"
        print("[CMD] PARADA DE EMERGENCIA")
        
    elif cmd_type == "request_status":
        status = {
            "type": "status_response",
            "zones": zone_readings,
            "drone": asdict(drone_state),
            "humidityZones": calcular_zonas_humedad(),
        }
        await websocket.send(json.dumps(status))
        
    # Notificar a todos los clientes del cambio de estado
    update = {
        "type": "drone_status_update",
        "drone": asdict(drone_state),
    }
    for client in connected_clients:
        await client.send(json.dumps(update))

# ── Punto de entrada ──────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  PUENTE UDP-WEBSOCKET - SISTEMA DE RIEGO AUTONOMO")
    print("  Universidad Popular del Cesar")
    print("=" * 60)
    print()
    print(f"  UDP:       {UDP_HOST}:{UDP_PORT}")
    print(f"  WebSocket: ws://{WS_HOST}:{WS_PORT}")
    print()
    print("  Esperando conexiones...")
    print()
    
    # Iniciar servidor WebSocket
    ws_server = await websockets.serve(websocket_handler, WS_HOST, WS_PORT)
    
    # Iniciar receptor UDP
    udp_task = asyncio.create_task(udp_receiver())
    
    # Mantener ambos corriendo
    await asyncio.gather(
        ws_server.wait_closed(),
        udp_task,
        return_exceptions=True
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SISTEMA] Apagando servidor...")
