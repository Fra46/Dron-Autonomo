"""
sensor_mock.py — Simulador de sensores de humedad del suelo
Proyecto: Sistema Inteligente de Control Autónomo para Drones de Riego
Universidad Popular del Cesar

Simula tres zonas de cultivo (norte / centro / sur) con rangos de humedad
distintos y envía cada lectura como JSON al controlador del Crazyflie.

Uso:
    python sensor_mock.py

El controlador debe estar escuchando en 127.0.0.1:5005 antes de iniciar.
"""

import socket
import json
import random
import time
import itertools

# ── Configuración de red ──────────────────────────────────────────────────────
DESTINO_IP     = "127.0.0.1"   # localhost: mismo equipo que Webots
DESTINO_PUERTO = 5005           # debe coincidir con UDP_PORT en el controlador

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ── Definición de zonas ───────────────────────────────────────────────────────
# Cada zona representa un sector del cultivo con su rango de humedad típico.
# Las zonas se recorren en ciclo; cada una aparece UNA sola vez por ciclo
# para evitar duplicados innecesarios.
ZONAS = [
    {"nombre": "norte",  "humedad_min": 65, "humedad_max": 90},
    {"nombre": "centro", "humedad_min": 40, "humedad_max": 64},
    {"nombre": "sur",    "humedad_min": 15, "humedad_max": 39},
]

ciclo_zonas = itertools.cycle(ZONAS)

# ── Lógica de interpretación ──────────────────────────────────────────────────
def interpretar_humedad(humedad: int) -> str:
    """
    Clasifica el nivel de humedad del suelo en cuatro estados.
    Umbrales basados en valores típicos de suelo arcillo-limoso tropical
    (referencia: IGAC, 2018; sección 8.3 del proyecto).
    """
    if humedad >= 70:
        return "humedo"
    elif humedad >= 50:
        return "normal"
    elif humedad >= 30:
        return "seco"
    else:
        return "muy_seco"     # ← activa el riego en el controlador


def generar_datos(zona: dict) -> dict:
    """
    Genera una lectura sintética para la zona indicada.
    Retorna un diccionario listo para serializar como JSON.
    """
    humedad = random.randint(zona["humedad_min"], zona["humedad_max"])
    return {
        "zona"        : zona["nombre"],
        "humedad"     : humedad,                                    # % saturación (0-100)
        "temperatura" : round(random.uniform(25.0, 35.0), 1),      # °C
        "bateria"     : random.randint(60, 100),                    # % batería del nodo
        "estado_suelo": interpretar_humedad(humedad),
    }


# ── Bucle principal ───────────────────────────────────────────────────────────
print("=" * 55)
print("  SIMULADOR DE SENSORES — DRONE DE RIEGO (Crazyflie)")
print("  Destino:", DESTINO_IP, "| Puerto:", DESTINO_PUERTO)
print("=" * 55)
print()

try:
    while True:
        zona  = next(ciclo_zonas)
        datos = generar_datos(zona)

        # Serializar a JSON y enviar por UDP
        mensaje = json.dumps(datos).encode("utf-8")
        sock.sendto(mensaje, (DESTINO_IP, DESTINO_PUERTO))

        # Indicador visual en consola
        estado_emoji = {
            "humedo"  : "💧",
            "normal"  : "✅",
            "seco"    : "⚠️ ",
            "muy_seco": "🔴",
        }.get(datos["estado_suelo"], "?")

        print(
            f"  {estado_emoji}  Zona: {datos['zona']:<8} | "
            f"Humedad: {datos['humedad']:>3}% | "
            f"Temp: {datos['temperatura']:>4}°C | "
            f"Batería: {datos['bateria']:>3}% | "
            f"Estado: {datos['estado_suelo']}"
        )

        time.sleep(1)   # Una lectura por segundo 
        if datos["estado_suelo"] == "muy_seco":
            time.sleep(30)   # Pausa adicional para simular riego activo

except KeyboardInterrupt:
    print()
    print("Simulación detenida por el usuario.")
finally:
    sock.close()