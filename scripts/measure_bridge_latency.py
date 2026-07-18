import asyncio
import argparse
import json
import socket
import time
import uuid
from collections import defaultdict
from statistics import mean, stdev

import websockets


def make_probe_message(probe_id: str, send_ts: float, zone: str, humidity: float, temperature: float, estado: str):
    return json.dumps({
        "zona": zone,
        "humedad": humidity,
        "estado_suelo": estado,
        "temperatura": temperature,
        "probe_id": probe_id,
        "send_ts": send_ts,
    }).encode("utf-8")


async def run_measurement(host: str, udp_port: int, ws_url: str, samples: int, interval: float):
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setblocking(False)
    loop = asyncio.get_running_loop()

    latencies = []
    results = []
    pending = {}
    received = set()

    async def websocket_listener():
        nonlocal latencies
        async with websockets.connect(ws_url) as ws:
            print(f"[WS] Conectado a {ws_url}")
            while len(received) < samples:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    print(f"[WS] Sin nuevas muestras en 2s (recibidas {len(received)}/{samples}); cerrando.")
                    break
                data = json.loads(message)
                if data.get("type") != "telemetry_update":
                    continue

                last = data.get("lastReading", {})
                probe_id = last.get("probe_id")
                send_ts = last.get("send_ts")
                if probe_id is None or send_ts is None:
                    continue

                if probe_id in received:
                    continue

                recv_ts = time.perf_counter()
                latency_ms = (recv_ts - float(send_ts)) * 1000.0
                latencies.append(latency_ms)
                received.add(probe_id)
                results.append(latency_ms)
                print(f"[{len(received)}/{samples}] probe_id={probe_id} latency={latency_ms:.2f} ms")

    async def udp_sender():
        nonlocal pending
        zones = [
            ("norte", 45.0, 30.0, "seco"),
            ("centro", 55.0, 32.0, "normal"),
            ("sur", 25.0, 35.0, "muy_seco"),
        ]
        for i in range(samples):
            zone, humidity, temperature, estado = zones[i % len(zones)]
            probe_id = str(uuid.uuid4())
            send_ts = time.perf_counter()
            packet = make_probe_message(probe_id, send_ts, zone, humidity, temperature, estado)
            udp_sock.sendto(packet, (host, udp_port))
            pending[probe_id] = send_ts
            await asyncio.sleep(interval)
        print(f"[UDP] Enviados {samples} paquetes de prueba")

    await asyncio.gather(websocket_listener(), udp_sender())

    return latencies


def summarize(latencies):
    if not latencies:
        return None
    return {
        "count": len(latencies),
        "mean_ms": mean(latencies),
        "stdev_ms": stdev(latencies) if len(latencies) > 1 else 0.0,
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "p95_ms": sorted(latencies)[int(len(latencies) * 0.95) - 1] if len(latencies) >= 20 else None,
        "p99_ms": sorted(latencies)[int(len(latencies) * 0.99) - 1] if len(latencies) >= 100 else None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Medir latencia real del puente UDP-WebSocket de AgroDrone")
    parser.add_argument("--host", default="127.0.0.1", help="Host UDP del puente")
    parser.add_argument("--udp-port", type=int, default=5005, help="Puerto UDP del puente")
    parser.add_argument("--ws-url", default="ws://localhost:8765", help="URL WebSocket del puente")
    parser.add_argument("--samples", type=int, default=300, help="Numero de muestras a recolectar")
    parser.add_argument("--interval", type=float, default=0.05, help="Intervalo en segundos entre paquetes UDP")
    args = parser.parse_args()

    try:
        latencies = asyncio.run(run_measurement(args.host, args.udp_port, args.ws_url, args.samples, args.interval))
        stats = summarize(latencies)
        if stats is None:
            print("No se recibieron latencias. Verifica que el puente UDP-WebSocket esté en ejecución.")
        else:
            print("\n--- Resultados de latencia ---")
            print(f"Muestras: {stats['count']}")
            print(f"Media: {stats['mean_ms']:.2f} ms")
            print(f"Desviación estándar: {stats['stdev_ms']:.2f} ms")
            print(f"Mínimo: {stats['min_ms']:.2f} ms")
            print(f"Máximo: {stats['max_ms']:.2f} ms")
            print(f"P95: {stats['p95_ms']:.2f} ms")
            if stats['p99_ms'] is not None:
                print(f"P99: {stats['p99_ms']:.2f} ms")
    except Exception as e:
        print(f"Error durante la medición: {e}")
