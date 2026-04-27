#!/usr/bin/env python3
"""
Servidor UDP de Telemetria para AgroDrone PWA
=============================================

Este servidor empaqueta datos de telemetria del dron (coordenadas, bateria, 
estado de riego) y los envia via UDP a la red local para que la PWA los reciba.

El frontend se conecta a traves de un WebSocket bridge que traduce UDP a WebSocket.

Uso:
    python udp_telemetry_server.py [--host HOST] [--port PORT] [--ws-port WS_PORT]

Ejemplo:
    python udp_telemetry_server.py --host 0.0.0.0 --port 5000 --ws-port 8765

Protocolo de paquetes UDP:
    - Tipo 0x01: Posicion (lat, lon, alt, bateria, velocidad)
    - Tipo 0x02: Lecturas de humedad (nodos)
    - Tipo 0x03: Estado de irrigacion (estado, nivel agua, flujo)
"""

import asyncio
import json
import struct
import socket
import argparse
import time
import random
import math
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("Advertencia: websockets no instalado. Solo modo UDP disponible.")
    print("Instalar con: pip install websockets")


@dataclass
class DronePosition:
    latitude: float = 4.5709
    longitude: float = -74.2973
    altitude: float = 0.0
    

@dataclass
class TelemetryData:
    # Posicion y estado del dron
    coordinates: DronePosition = None
    battery: float = 100.0
    signal: float = 95.0
    speed: float = 0.0
    temperature: float = 25.0
    flight_status: str = "idle"  # idle, takeoff, flying, spraying, returning, landing
    
    # Datos de irrigacion
    irrigation_status: str = "inactive"  # inactive, active, paused
    water_level: float = 100.0
    flow_rate: float = 0.0
    
    # Datos de terreno
    average_humidity: float = 48.0
    node_readings: List[Dict] = None
    
    # Timestamps
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.coordinates is None:
            self.coordinates = DronePosition()
        if self.node_readings is None:
            self.node_readings = []
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def to_json(self) -> str:
        data = asdict(self)
        data['coordinates'] = asdict(self.coordinates)
        return json.dumps(data)
    
    def to_binary_position(self) -> bytes:
        """Empaqueta datos de posicion en formato binario (Tipo 0x01)"""
        return struct.pack(
            '<BffffB',  # Little-endian: tipo, lat, lon, alt, velocidad, bateria
            0x01,
            self.coordinates.latitude,
            self.coordinates.longitude,
            self.coordinates.altitude,
            self.speed,
            int(self.battery)
        )
    
    def to_binary_humidity(self) -> bytes:
        """Empaqueta lecturas de humedad en formato binario (Tipo 0x02)"""
        packet = struct.pack('<BB', 0x02, len(self.node_readings))
        
        for node in self.node_readings:
            node_id = node['id'].encode('utf-8')
            packet += struct.pack('<B', len(node_id))
            packet += node_id
            packet += struct.pack(
                '<Bff',
                int(node['humidity']),
                node['x'],
                node['y']
            )
        
        return packet
    
    def to_binary_irrigation(self) -> bytes:
        """Empaqueta estado de irrigacion en formato binario (Tipo 0x03)"""
        status_map = {'inactive': 0, 'active': 1, 'paused': 2}
        return struct.pack(
            '<BBBf',
            0x03,
            status_map.get(self.irrigation_status, 0),
            int(self.water_level),
            self.flow_rate
        )


class DroneSimulator:
    """Simulador de dron para pruebas sin hardware real"""
    
    INITIAL_NODES = [
        {'id': 'A1', 'x': 15, 'y': 15, 'humidity': 35},
        {'id': 'A2', 'x': 50, 'y': 10, 'humidity': 62},
        {'id': 'A3', 'x': 85, 'y': 15, 'humidity': 78},
        {'id': 'B1', 'x': 10, 'y': 50, 'humidity': 45},
        {'id': 'B2', 'x': 50, 'y': 50, 'humidity': 28},
        {'id': 'B3', 'x': 90, 'y': 50, 'humidity': 55},
        {'id': 'C1', 'x': 15, 'y': 85, 'humidity': 72},
        {'id': 'C2', 'x': 50, 'y': 90, 'humidity': 41},
        {'id': 'C3', 'x': 85, 'y': 85, 'humidity': 88},
    ]
    
    def __init__(self):
        self.telemetry = TelemetryData()
        self.telemetry.node_readings = [dict(n, lastUpdated=time.time()) for n in self.INITIAL_NODES]
        self._update_average_humidity()
        
        self.drone_x = 50.0
        self.drone_y = 95.0
        self.target_node_index = 0
        self.mission_start_time: Optional[float] = None
    
    def _update_average_humidity(self):
        if self.telemetry.node_readings:
            self.telemetry.average_humidity = sum(
                n['humidity'] for n in self.telemetry.node_readings
            ) / len(self.telemetry.node_readings)
    
    def start_mission(self):
        """Inicia mision autonoma"""
        self.telemetry.flight_status = "takeoff"
        self.mission_start_time = time.time()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Mision iniciada - Despegando...")
    
    def stop_mission(self):
        """Detiene mision y retorna a base"""
        self.telemetry.flight_status = "returning"
        self.telemetry.irrigation_status = "inactive"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Mision detenida - Retornando...")
    
    def update(self) -> TelemetryData:
        """Actualiza simulacion y retorna telemetria"""
        now = time.time()
        
        # Actualizar timestamp
        self.telemetry.timestamp = now
        
        # Simulacion de estados de vuelo
        if self.telemetry.flight_status == "takeoff":
            self.telemetry.coordinates.altitude = min(15, self.telemetry.coordinates.altitude + 0.5)
            if self.telemetry.coordinates.altitude >= 15:
                self.telemetry.flight_status = "flying"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Altitud alcanzada - En vuelo")
        
        elif self.telemetry.flight_status == "flying":
            # Buscar nodos con baja humedad
            low_humidity_nodes = [n for n in self.telemetry.node_readings if n['humidity'] < 50]
            
            if low_humidity_nodes:
                target = low_humidity_nodes[self.target_node_index % len(low_humidity_nodes)]
                
                # Mover hacia el objetivo
                dx = target['x'] - self.drone_x
                dy = target['y'] - self.drone_y
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance < 3:
                    # Llegamos al nodo, activar riego
                    self.telemetry.flight_status = "spraying"
                    self.telemetry.irrigation_status = "active"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Regando nodo {target['id']}")
                else:
                    # Moverse hacia el objetivo
                    speed = 2
                    self.drone_x += (dx / distance) * speed
                    self.drone_y += (dy / distance) * speed
                    self.telemetry.speed = 4 + random.random() * 2
            else:
                # Todos los nodos estan bien, retornar
                self.telemetry.flight_status = "returning"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Mision completada - Retornando")
        
        elif self.telemetry.flight_status == "spraying":
            # Regar el nodo actual
            low_humidity_nodes = [n for n in self.telemetry.node_readings if n['humidity'] < 50]
            if low_humidity_nodes:
                target = low_humidity_nodes[self.target_node_index % len(low_humidity_nodes)]
                
                # Aumentar humedad del nodo
                for node in self.telemetry.node_readings:
                    if node['id'] == target['id']:
                        node['humidity'] = min(100, node['humidity'] + 5)
                        node['lastUpdated'] = now
                        
                        if node['humidity'] >= 50:
                            self.target_node_index += 1
                            self.telemetry.flight_status = "flying"
                            self.telemetry.irrigation_status = "inactive"
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Nodo {target['id']} completado")
                        break
            
            # Consumir agua
            self.telemetry.water_level = max(0, self.telemetry.water_level - 0.5)
            self.telemetry.flow_rate = 2.5 + random.random() * 0.5
        
        elif self.telemetry.flight_status == "returning":
            # Volver a la base
            dx = 50 - self.drone_x
            dy = 95 - self.drone_y
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance < 3:
                self.telemetry.flight_status = "landing"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando aterrizaje")
            else:
                speed = 3
                self.drone_x += (dx / distance) * speed
                self.drone_y += (dy / distance) * speed
                self.telemetry.speed = 5 + random.random() * 2
        
        elif self.telemetry.flight_status == "landing":
            self.telemetry.coordinates.altitude = max(0, self.telemetry.coordinates.altitude - 0.5)
            if self.telemetry.coordinates.altitude <= 0:
                self.telemetry.flight_status = "idle"
                self.telemetry.speed = 0
                self.drone_x = 50
                self.drone_y = 95
                self.target_node_index = 0
                self.mission_start_time = None
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Dron en tierra - Listo")
        
        # Actualizaciones generales
        if self.telemetry.flight_status != "idle":
            # Consumo de bateria en vuelo
            self.telemetry.battery = max(0, self.telemetry.battery - 0.05)
        
        # Variaciones de senal
        self.telemetry.signal = min(100, max(70, self.telemetry.signal + (random.random() - 0.5) * 5))
        
        # Variaciones de temperatura
        self.telemetry.temperature = 28 + random.random() * 2
        
        # Actualizar humedad promedio
        self._update_average_humidity()
        
        # Simular cambios naturales de humedad en los nodos (evaporacion)
        for node in self.telemetry.node_readings:
            if self.telemetry.flight_status != "spraying" or node['humidity'] >= 50:
                node['humidity'] = max(5, node['humidity'] - random.random() * 0.3)
        
        return self.telemetry


class TelemetryServer:
    """Servidor UDP con bridge WebSocket para la PWA"""
    
    def __init__(self, host: str = '0.0.0.0', udp_port: int = 5000, ws_port: int = 8765):
        self.host = host
        self.udp_port = udp_port
        self.ws_port = ws_port
        self.simulator = DroneSimulator()
        self.ws_clients: set = set()
        self.running = False
    
    async def broadcast_telemetry(self, telemetry: TelemetryData):
        """Envia telemetria a todos los clientes WebSocket"""
        if not self.ws_clients:
            return
        
        message = telemetry.to_json()
        disconnected = set()
        
        for ws in self.ws_clients:
            try:
                await ws.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(ws)
            except Exception as e:
                print(f"Error enviando a cliente: {e}")
                disconnected.add(ws)
        
        self.ws_clients -= disconnected
    
    async def handle_ws_client(self, websocket, path):
        """Maneja conexiones WebSocket entrantes"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cliente WebSocket conectado: {websocket.remote_address}")
        self.ws_clients.add(websocket)
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    command_type = data.get('type')
                    
                    if command_type == 'flight_status':
                        status = data.get('status')
                        if status == 'takeoff':
                            self.simulator.start_mission()
                        elif status in ('returning', 'idle'):
                            self.simulator.stop_mission()
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Comando recibido: flight_status = {status}")
                    
                    elif command_type == 'irrigation_status':
                        status = data.get('status')
                        self.simulator.telemetry.irrigation_status = status
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Comando recibido: irrigation_status = {status}")
                    
                except json.JSONDecodeError:
                    print(f"Mensaje invalido recibido: {message}")
        
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.ws_clients.discard(websocket)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cliente WebSocket desconectado")
    
    def send_udp_packet(self, sock: socket.socket, data: bytes, address: tuple):
        """Envia paquete UDP"""
        try:
            sock.sendto(data, address)
        except Exception as e:
            print(f"Error enviando UDP: {e}")
    
    async def telemetry_loop(self):
        """Loop principal de actualizacion de telemetria"""
        # Crear socket UDP
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Servidor de telemetria iniciado")
        print(f"  UDP: {self.host}:{self.udp_port}")
        if HAS_WEBSOCKETS:
            print(f"  WebSocket: ws://{self.host}:{self.ws_port}")
        print()
        
        while self.running:
            # Actualizar simulacion
            telemetry = self.simulator.update()
            
            # Enviar por UDP (broadcast)
            broadcast_addr = ('<broadcast>', self.udp_port)
            
            # Enviar diferentes tipos de paquetes
            self.send_udp_packet(udp_sock, telemetry.to_binary_position(), broadcast_addr)
            self.send_udp_packet(udp_sock, telemetry.to_binary_humidity(), broadcast_addr)
            self.send_udp_packet(udp_sock, telemetry.to_binary_irrigation(), broadcast_addr)
            
            # Enviar por WebSocket (JSON)
            await self.broadcast_telemetry(telemetry)
            
            # Esperar antes de la siguiente actualizacion
            await asyncio.sleep(1.0)  # 1 Hz
        
        udp_sock.close()
    
    async def run(self):
        """Inicia el servidor"""
        self.running = True
        
        tasks = [self.telemetry_loop()]
        
        if HAS_WEBSOCKETS:
            # Iniciar servidor WebSocket
            ws_server = await websockets.serve(
                self.handle_ws_client,
                self.host,
                self.ws_port
            )
            print(f"Servidor WebSocket escuchando en ws://{self.host}:{self.ws_port}")
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            if HAS_WEBSOCKETS:
                ws_server.close()
                await ws_server.wait_closed()


def main():
    parser = argparse.ArgumentParser(description='Servidor UDP de Telemetria para AgroDrone')
    parser.add_argument('--host', default='0.0.0.0', help='Host del servidor (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Puerto UDP (default: 5000)')
    parser.add_argument('--ws-port', type=int, default=8765, help='Puerto WebSocket (default: 8765)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  SERVIDOR DE TELEMETRIA AGRODRONE")
    print("  Sistema de Riego Autonomo Inteligente")
    print("=" * 60)
    print()
    
    server = TelemetryServer(
        host=args.host,
        udp_port=args.port,
        ws_port=args.ws_port
    )
    
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario")


if __name__ == '__main__':
    main()
